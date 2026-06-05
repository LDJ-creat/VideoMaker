from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import Any


_TEMPO_FAST_SEC = 1.2
_TEMPO_SLOW_SEC = 2.8
_TEMPO_CV_MIXED = 0.65


class KeyframeEncodingError(ValueError):
    """Raised when keyframe metadata exists but no encodable image files are found."""


def _shot_duration(shot: dict[str, Any]) -> float:
    return float(shot["endSec"]) - float(shot["startSec"])


def compute_rhythm_facts(
    shots: list[dict[str, Any]],
    *,
    duration_sec: float | None = None,
) -> dict[str, Any]:
    if not shots:
        return {
            "shotCount": 0,
            "avgShotDurationSec": 0.0,
            "tempoHint": "slow",
            "durationSec": duration_sec or 0.0,
        }

    durations = [_shot_duration(shot) for shot in shots]
    avg = sum(durations) / len(durations)
    if len(durations) > 1 and avg > 0:
        variance = sum((value - avg) ** 2 for value in durations) / len(durations)
        cv = (variance**0.5) / avg
    else:
        cv = 0.0

    if cv > _TEMPO_CV_MIXED:
        tempo_hint = "mixed"
    elif avg < _TEMPO_FAST_SEC:
        tempo_hint = "fast"
    elif avg <= _TEMPO_SLOW_SEC:
        tempo_hint = "medium"
    else:
        tempo_hint = "slow"

    return {
        "shotCount": len(shots),
        "avgShotDurationSec": round(avg, 3),
        "tempoHint": tempo_hint,
        "durationSec": duration_sec if duration_sec is not None else shots[-1]["endSec"],
    }


def _pick_best_keyframes_per_shot(keyframes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    best_by_shot: dict[str, dict[str, Any]] = {}
    for frame in keyframes:
        shot_id = str(frame.get("shotId", ""))
        if not shot_id:
            continue
        current = best_by_shot.get(shot_id)
        if current is None or float(frame.get("score", 0)) > float(current.get("score", 0)):
            best_by_shot[shot_id] = frame
    return sorted(best_by_shot.values(), key=lambda item: float(item.get("timeSec", 0)))


def _evenly_sample(items: list[dict[str, Any]], count: int) -> list[dict[str, Any]]:
    if len(items) <= count:
        return items
    if count <= 1:
        return [items[0]]
    step = (len(items) - 1) / (count - 1)
    indices = {round(index * step) for index in range(count)}
    ordered = sorted(indices)
    return [items[index] for index in ordered]


def _guess_mime_type(path: Path) -> str:
    mime, _ = mimetypes.guess_type(path.name)
    return mime or "image/jpeg"


def _resolve_keyframe_path(analysis_root: Path, rel_path: str) -> Path | None:
    root = analysis_root.resolve()
    candidate = (root / rel_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate


def _encode_keyframes(
    keyframes: list[dict[str, Any]],
    *,
    analysis_root: Path,
    max_keyframes: int,
) -> list[dict[str, Any]]:
    selected = _evenly_sample(_pick_best_keyframes_per_shot(keyframes), max_keyframes)
    encoded: list[dict[str, Any]] = []
    for frame in selected:
        rel_path = frame.get("path")
        if not rel_path:
            continue
        image_path = _resolve_keyframe_path(analysis_root, str(rel_path))
        if image_path is None or not image_path.is_file():
            continue
        encoded.append(
            {
                "shotId": frame.get("shotId"),
                "timeSec": frame.get("timeSec"),
                "path": str(rel_path),
                "imageBase64": base64.b64encode(image_path.read_bytes()).decode("ascii"),
                "mimeType": _guess_mime_type(image_path),
            }
        )
    return encoded


def build_structure_analyst_inputs(
    analysis: dict[str, Any],
    *,
    analysis_root: Path | None = None,
    max_keyframes: int = 8,
    require_keyframe_files: bool = False,
) -> dict[str, Any]:
    metadata = analysis.get("metadata", {})
    shots = list(analysis.get("shots", []))
    duration_sec = metadata.get("durationSec")
    payload: dict[str, Any] = {
        "metadata": metadata,
        "transcript": list(analysis.get("transcript", [])),
        "shots": shots,
        "rhythmFacts": compute_rhythm_facts(shots, duration_sec=duration_sec),
        "locale": str(analysis.get("locale") or "zh"),
    }

    audio_profile = analysis.get("audioProfile")
    if isinstance(audio_profile, dict):
        payload["audioProfile"] = audio_profile

    batch_digests = analysis.get("keyframeBatchDigests")
    if isinstance(batch_digests, list):
        payload["keyframeBatchDigests"] = batch_digests

    raw_keyframes = list(analysis.get("keyframes", []))
    if analysis_root is not None and raw_keyframes:
        encoded = _encode_keyframes(
            raw_keyframes,
            analysis_root=analysis_root,
            max_keyframes=max_keyframes,
        )
        if encoded:
            payload["keyframes"] = encoded
        elif require_keyframe_files:
            raise KeyframeEncodingError(
                "sample analysis lists keyframes but no readable image files were found "
                f"under {analysis_root}"
            )
    return payload
