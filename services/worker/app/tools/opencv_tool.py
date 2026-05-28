from __future__ import annotations

import json
import math
import statistics
from pathlib import Path
from typing import Any


def _tool_error(code: str, message: str, retryable: bool = True) -> dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "retryable": retryable,
    }


def build_shot_boundaries(
    distances: list[float],
    sample_times: list[float],
    duration_sec: float,
    min_shot_duration_sec: float = 0.45,
) -> list[dict[str, Any]]:
    if not distances or len(sample_times) < 2:
        return [
            {
                "startSec": 0.0,
                "endSec": round(duration_sec, 3),
                "confidence": 0.4,
                "changeReason": "unknown",
            }
        ]

    median = statistics.median(distances)
    mad = statistics.median([abs(item - median) for item in distances]) if distances else 0.0
    threshold = min(0.75, max(0.35, median + 3 * mad))

    cuts: list[tuple[float, float]] = []
    last_boundary = 0.0
    for idx, distance in enumerate(distances):
        cut_time = sample_times[idx + 1]
        if distance > threshold and cut_time - last_boundary >= min_shot_duration_sec:
            cuts.append((cut_time, distance))
            last_boundary = cut_time

    if not cuts:
        return [
            {
                "startSec": 0.0,
                "endSec": round(duration_sec, 3),
                "confidence": 0.4,
                "changeReason": "unknown",
            }
        ]

    boundaries = [0.0] + [time for time, _ in cuts] + [duration_sec]
    score_by_boundary = {time: dist for time, dist in cuts}

    shots: list[dict[str, Any]] = []
    for start, end in zip(boundaries[:-1], boundaries[1:]):
        confidence_source = score_by_boundary.get(end, threshold)
        confidence = min(1.0, max(0.45, confidence_source / threshold))
        shots.append(
            {
                "startSec": round(start, 3),
                "endSec": round(end, 3),
                "confidence": round(confidence, 3),
                "changeReason": "histogram_cut",
            }
        )

    merged: list[dict[str, Any]] = []
    for shot in shots:
        duration = shot["endSec"] - shot["startSec"]
        if duration < 0.35 and merged:
            merged[-1]["endSec"] = shot["endSec"]
            merged[-1]["confidence"] = max(merged[-1]["confidence"], shot["confidence"])
        else:
            merged.append(shot)

    return merged or [
        {
            "startSec": 0.0,
            "endSec": round(duration_sec, 3),
            "confidence": 0.4,
            "changeReason": "unknown",
        }
    ]


def score_keyframe_candidates(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not candidates:
        return None

    sharpness_values = [candidate["sharpness"] for candidate in candidates]
    entropy_values = [candidate["entropy"] for candidate in candidates]
    sharp_min, sharp_max = min(sharpness_values), max(sharpness_values)
    entropy_min, entropy_max = min(entropy_values), max(entropy_values)

    def normalize(value: float, minimum: float, maximum: float) -> float:
        if maximum == minimum:
            return 1.0
        return (value - minimum) / (maximum - minimum)

    scored: list[dict[str, Any]] = []
    for candidate in candidates:
        exposure_penalty = abs(candidate["meanBrightness"] - 128.0) / 128.0
        score = (
            normalize(candidate["sharpness"], sharp_min, sharp_max) * 0.6
            + normalize(candidate["entropy"], entropy_min, entropy_max) * 0.3
            - exposure_penalty * 0.1
        )
        updated = dict(candidate)
        updated["score"] = round(score, 6)
        scored.append(updated)

    return max(scored, key=lambda item: item["score"])


class OpenCVTool:
    def __init__(self, cv2_module: Any = "auto") -> None:
        if cv2_module == "auto":
            try:
                import cv2 as imported_cv2  # type: ignore
            except ImportError:
                imported_cv2 = None
            self.cv2 = imported_cv2
        else:
            self.cv2 = cv2_module

    def detect_shots(
        self,
        video_path: str | Path,
        *,
        duration_sec: float | None = None,
        output_json_path: str | Path | None = None,
    ) -> dict[str, Any]:
        if self.cv2 is None:
            return self._fallback_shots(duration_sec, "opencv_missing")

        capture = self.cv2.VideoCapture(str(Path(video_path).resolve()))
        if not capture.isOpened():
            return self._fallback_shots(duration_sec, "opencv_video_open_failed")

        fps = float(capture.get(self.cv2.CAP_PROP_FPS) or 0.0)
        frame_count = int(capture.get(self.cv2.CAP_PROP_FRAME_COUNT) or 0)
        video_duration = duration_sec if duration_sec is not None else (frame_count / fps if fps > 0 else 0.0)
        sampling_step = max(1, int(round(fps / 3.0))) if fps > 0 else 1

        frame_histograms: list[Any] = []
        sample_times: list[float] = []
        frame_index = 0
        while True:
            capture.set(self.cv2.CAP_PROP_POS_FRAMES, frame_index)
            success, frame = capture.read()
            if not success:
                break
            hsv = self.cv2.cvtColor(frame, self.cv2.COLOR_BGR2HSV)
            histogram = self.cv2.calcHist([hsv], [0, 1], None, [50, 60], [0, 180, 0, 256])
            histogram = self.cv2.normalize(histogram, histogram).flatten()
            frame_histograms.append(histogram)
            sample_times.append(frame_index / fps if fps > 0 else 0.0)
            frame_index += sampling_step

        capture.release()
        if frame_histograms:
            sample_times.append(video_duration or sample_times[-1])

        distances: list[float] = []
        for prev, curr in zip(frame_histograms[:-1], frame_histograms[1:]):
            distance = 1 - float(self.cv2.compareHist(prev, curr, self.cv2.HISTCMP_CORREL))
            distances.append(distance)

        shots = build_shot_boundaries(distances, sample_times, max(video_duration, 0.0))
        result: dict[str, Any] = {"shots": shots}
        if output_json_path is not None:
            output_path = Path(output_json_path).resolve()
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(shots, ensure_ascii=False, indent=2), encoding="utf-8")
        return result

    def extract_keyframes(
        self,
        video_path: str | Path,
        shots: list[dict[str, Any]],
        output_dir: str | Path,
        *,
        keyframes_json_path: str | Path | None = None,
    ) -> dict[str, Any]:
        if self.cv2 is None:
            return {
                "keyframes": [],
                "warning": _tool_error("opencv_missing", "opencv-python is not installed"),
            }

        capture = self.cv2.VideoCapture(str(Path(video_path).resolve()))
        if not capture.isOpened():
            return {
                "keyframes": [],
                "warning": _tool_error("opencv_video_open_failed", "video file cannot be opened"),
            }

        output_root = Path(output_dir).resolve()
        output_root.mkdir(parents=True, exist_ok=True)
        keyframes: list[dict[str, Any]] = []

        for idx, shot in enumerate(shots):
            start_sec = float(shot["startSec"])
            end_sec = float(shot["endSec"])
            duration = max(0.0, end_sec - start_sec)
            sample_offsets = [0.5] if duration < 0.8 else [0.2, 0.5, 0.8]

            candidates: list[dict[str, Any]] = []
            for offset in sample_offsets:
                time_sec = start_sec + duration * offset
                capture.set(self.cv2.CAP_PROP_POS_MSEC, max(0.0, time_sec * 1000.0))
                success, frame = capture.read()
                if not success:
                    continue

                gray = self.cv2.cvtColor(frame, self.cv2.COLOR_BGR2GRAY)
                laplacian = self.cv2.Laplacian(gray, self.cv2.CV_64F)
                sharpness = float(laplacian.var())
                histogram = self.cv2.calcHist([gray], [0], None, [256], [0, 256]).flatten()
                total = float(histogram.sum()) or 1.0
                probabilities = (histogram / total).tolist()
                entropy = -sum(p * math.log(p) for p in probabilities if p > 0)
                mean_brightness = float(gray.mean())

                candidates.append(
                    {
                        "timeSec": round(time_sec, 3),
                        "sharpness": sharpness,
                        "entropy": entropy,
                        "meanBrightness": mean_brightness,
                        "frame": frame,
                        "width": int(frame.shape[1]),
                        "height": int(frame.shape[0]),
                    }
                )

            best = score_keyframe_candidates(candidates)
            if best is None:
                midpoint = start_sec + duration / 2.0
                capture.set(self.cv2.CAP_PROP_POS_MSEC, max(0.0, midpoint * 1000.0))
                success, frame = capture.read()
                if not success:
                    continue
                best = {
                    "timeSec": round(midpoint, 3),
                    "score": 0.0,
                    "frame": frame,
                    "width": int(frame.shape[1]),
                    "height": int(frame.shape[0]),
                }

            time_ms = int(round(float(best["timeSec"]) * 1000))
            filename = f"shot-{idx}-{time_ms}.jpg"
            frame_path = output_root / filename
            self.cv2.imwrite(str(frame_path), best["frame"], [int(self.cv2.IMWRITE_JPEG_QUALITY), 88])
            keyframes.append(
                {
                    "shotId": f"shot-{idx}",
                    "timeSec": best["timeSec"],
                    "path": str(frame_path.resolve()),
                    "score": float(best["score"]),
                    "width": int(best["width"]),
                    "height": int(best["height"]),
                }
            )

        capture.release()
        if keyframes_json_path is not None:
            output_json = Path(keyframes_json_path).resolve()
            output_json.parent.mkdir(parents=True, exist_ok=True)
            output_json.write_text(json.dumps(keyframes, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"keyframes": keyframes}

    def _fallback_shots(self, duration_sec: float | None, code: str) -> dict[str, Any]:
        fallback_duration = round(duration_sec or 0.0, 3)
        return {
            "shots": [
                {
                    "startSec": 0.0,
                    "endSec": fallback_duration,
                    "confidence": 0.4,
                    "changeReason": "unknown",
                }
            ],
            "warning": _tool_error(code, "opencv shot detection unavailable"),
        }
