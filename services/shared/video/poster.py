from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

DEFAULT_SAMPLE_TIMES_SEC = (1.0, 1.5, 2.0)
FALLBACK_TIME_SEC = 1.5
SHORT_VIDEO_THRESHOLD_SEC = 2.5
MIN_TAIL_PADDING_SEC = 0.05


def sample_poster_path(storage_root: Path, project_id: str, sample_id: str) -> Path:
    return (
        Path(storage_root)
        / "projects"
        / project_id
        / "samples"
        / sample_id
        / "poster.jpg"
    )


def generation_poster_path(storage_root: Path, project_id: str, generation_id: str) -> Path:
    return (
        Path(storage_root)
        / "projects"
        / project_id
        / "renders"
        / generation_id
        / "poster.jpg"
    )


def _ffmpeg_extract_frame(video_path: Path, output_path: Path, time_sec: float) -> bool:
    command = [
        "ffmpeg",
        "-y",
        "-ss",
        f"{max(0.0, time_sec):.3f}",
        "-i",
        str(video_path.resolve()),
        "-frames:v",
        "1",
        "-q:v",
        "2",
        str(output_path),
    ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return False
    return result.returncode == 0 and output_path.is_file() and output_path.stat().st_size > 0


def _sharpness_score(image_path: Path) -> float | None:
    try:
        import cv2  # type: ignore
    except ImportError:
        return None

    image = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        return None
    laplacian = cv2.Laplacian(image, cv2.CV_64F)
    return float(laplacian.var())


def _probe_duration_sec(video_path: Path) -> float | None:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(video_path.resolve()),
    ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return None
    if result.returncode != 0:
        return None
    raw = (result.stdout or "").strip()
    if not raw:
        return None
    try:
        duration = float(raw)
    except ValueError:
        return None
    return duration if duration > 0 else None


def _clamp_time_sec(time_sec: float, duration_sec: float | None) -> float:
    clamped = max(0.0, time_sec)
    if duration_sec is None:
        return clamped
    upper = max(0.0, duration_sec - MIN_TAIL_PADDING_SEC)
    return min(clamped, upper)


def _build_sample_times(
    duration_sec: float | None,
    *,
    sample_times_sec: tuple[float, ...],
) -> tuple[float, ...]:
    if duration_sec is None:
        return sample_times_sec

    if duration_sec >= SHORT_VIDEO_THRESHOLD_SEC:
        template = sample_times_sec
    elif duration_sec >= 1.0:
        template = (0.5, 1.0, min(1.5, duration_sec - MIN_TAIL_PADDING_SEC))
    else:
        template = (0.0, 0.1, min(0.5, duration_sec - MIN_TAIL_PADDING_SEC))

    ordered: list[float] = []
    seen: set[float] = set()
    for time_sec in template:
        clamped = _clamp_time_sec(time_sec, duration_sec)
        key = round(clamped, 3)
        if key in seen:
            continue
        seen.add(key)
        ordered.append(clamped)
    return tuple(ordered) if ordered else (0.0,)


def _collect_candidates(
    video_path: Path,
    temp_dir: str,
    sample_times_sec: tuple[float, ...],
) -> list[tuple[float, Path, float | None]]:
    candidates: list[tuple[float, Path, float | None]] = []
    for time_sec in sample_times_sec:
        frame_path = Path(temp_dir) / f"frame-{time_sec:.3f}.jpg"
        if not _ffmpeg_extract_frame(video_path, frame_path, time_sec):
            continue
        candidates.append((time_sec, frame_path, _sharpness_score(frame_path)))
    return candidates


def _pick_best_candidate(
    candidates: list[tuple[float, Path, float | None]],
) -> tuple[float, Path]:
    scored = [item for item in candidates if item[2] is not None]
    if scored:
        best = max(scored, key=lambda item: float(item[2]))
        return best[0], best[1]

    for preferred in (FALLBACK_TIME_SEC, *DEFAULT_SAMPLE_TIMES_SEC):
        for time_sec, frame_path, _ in candidates:
            if time_sec == preferred:
                return time_sec, frame_path
    return candidates[0][0], candidates[0][1]


def extract_video_poster(
    video_path: Path,
    output_path: Path,
    *,
    sample_times_sec: tuple[float, ...] = DEFAULT_SAMPLE_TIMES_SEC,
    force: bool = False,
) -> dict[str, Any]:
    resolved_video = Path(video_path).resolve()
    resolved_output = Path(output_path).resolve()

    if not resolved_video.is_file():
        return {"ok": False, "error": "video_not_found"}

    if (
        not force
        and resolved_output.is_file()
        and resolved_output.stat().st_mtime >= resolved_video.stat().st_mtime
    ):
        return {"ok": True, "skipped": True}

    resolved_output.parent.mkdir(parents=True, exist_ok=True)

    duration_sec = _probe_duration_sec(resolved_video)
    primary_times = _build_sample_times(duration_sec, sample_times_sec=sample_times_sec)

    with tempfile.TemporaryDirectory(prefix="videomaker-poster-") as temp_dir:
        candidates = _collect_candidates(resolved_video, temp_dir, primary_times)
        if not candidates and primary_times != sample_times_sec:
            candidates = _collect_candidates(resolved_video, temp_dir, sample_times_sec)
        if not candidates and duration_sec is not None and duration_sec < SHORT_VIDEO_THRESHOLD_SEC:
            early_times = _build_sample_times(
                None,
                sample_times_sec=(0.0, 0.1, 0.5),
            )
            candidates = _collect_candidates(resolved_video, temp_dir, early_times)

        if not candidates:
            return {"ok": False, "error": "ffmpeg_extract_failed"}

        source_time_sec, best_frame = _pick_best_candidate(candidates)
        shutil.copy2(best_frame, resolved_output)

    return {
        "ok": True,
        "sourceTimeSec": source_time_sec,
        "skipped": False,
    }
