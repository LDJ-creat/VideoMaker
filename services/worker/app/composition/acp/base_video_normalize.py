from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.tools.ffmpeg_tool import FFmpegTool

_DEFAULT_MAX_KEYFRAME_SEC = 2.0
_SPARSE_INTERVAL_RE = re.compile(r"max interval:\s*([0-9.]+)s", re.I)


@dataclass(frozen=True)
class BaseVideoDiagnostics:
    max_keyframe_interval_sec: float | None
    reencoded: bool
    source_path: str | None = None
    normalized_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "reencoded": self.reencoded,
            "maxKeyframeIntervalSec": self.max_keyframe_interval_sec,
        }
        if self.source_path:
            payload["sourcePath"] = self.source_path
        if self.normalized_path:
            payload["normalizedPath"] = self.normalized_path
        return payload


def max_keyframe_interval_threshold_sec() -> float:
    raw = os.getenv("VIDEOMAKER_COMPOSITION_BASE_VIDEO_MAX_KEYFRAME_SEC", "").strip()
    if not raw:
        return _DEFAULT_MAX_KEYFRAME_SEC
    try:
        return max(0.5, float(raw))
    except ValueError:
        return _DEFAULT_MAX_KEYFRAME_SEC


def probe_keyframe_interval_sec(video_path: Path, *, ffmpeg: FFmpegTool | None = None) -> float | None:
    """Estimate max gap between consecutive keyframes via ffprobe packet timestamps."""
    resolved = Path(video_path).resolve()
    if not resolved.is_file() or resolved.stat().st_size <= 0:
        return None
    tool = ffmpeg or FFmpegTool()
    command = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-skip_frame",
        "nokey",
        "-show_entries",
        "frame=best_effort_timestamp_time",
        "-of",
        "csv=p=0",
        str(resolved),
    ]
    try:
        result = tool._command_runner(command)  # noqa: SLF001 — shared runner with FFmpegTool
    except FileNotFoundError:
        return None
    if result.returncode != 0:
        return None
    timestamps: list[float] = []
    for line in (result.stdout or "").splitlines():
        token = line.strip()
        if not token:
            continue
        try:
            timestamps.append(float(token))
        except ValueError:
            continue
    if len(timestamps) < 2:
        probe = tool.probe(resolved)
        if isinstance(probe, dict) and not probe.get("code"):
            duration = float(probe.get("durationSec") or 0.0)
            if duration > 0:
                return duration
        return None
    max_gap = 0.0
    previous = timestamps[0]
    for current in timestamps[1:]:
        max_gap = max(max_gap, current - previous)
        previous = current
    return round(max_gap, 3)


def parse_sparse_keyframe_warning(stderr_or_stdout: str) -> float | None:
    match = _SPARSE_INTERVAL_RE.search(stderr_or_stdout or "")
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def should_normalize_base_video(interval_sec: float | None, *, threshold_sec: float | None = None) -> bool:
    if interval_sec is None:
        return False
    threshold = threshold_sec if threshold_sec is not None else max_keyframe_interval_threshold_sec()
    return interval_sec > threshold


def normalize_base_video_for_composition(
    src: Path,
    dest: Path,
    *,
    ffmpeg: FFmpegTool | None = None,
) -> dict[str, Any]:
    tool = ffmpeg or FFmpegTool()
    return tool.normalize_for_composition_preview(src, dest)


def prepare_base_video_for_scratch(
    src: Path,
    scratch_dir: Path,
    *,
    ffmpeg: FFmpegTool | None = None,
    cache_basename: str | None = None,
) -> tuple[Path, BaseVideoDiagnostics]:
    """Copy or re-encode base video into scratch when keyframes are too sparse."""
    scratch_dir.mkdir(parents=True, exist_ok=True)
    resolved_src = src.resolve()
    interval = probe_keyframe_interval_sec(resolved_src, ffmpeg=ffmpeg)
    threshold = max_keyframe_interval_threshold_sec()
    if cache_basename:
        dest_name = cache_basename
    elif should_normalize_base_video(interval, threshold_sec=threshold):
        stem = resolved_src.stem
        dest_name = f"{stem}-normalized.mp4"
    else:
        dest_name = resolved_src.name
    dest = scratch_dir / dest_name

    if not should_normalize_base_video(interval, threshold_sec=threshold):
        if dest.resolve() != resolved_src.resolve():
            dest.write_bytes(resolved_src.read_bytes())
        return dest, BaseVideoDiagnostics(
            max_keyframe_interval_sec=interval,
            reencoded=False,
            source_path=str(resolved_src),
            normalized_path=str(dest),
        )

    if dest.is_file() and dest.stat().st_size > 0 and dest.stat().st_mtime >= resolved_src.stat().st_mtime:
        return dest, BaseVideoDiagnostics(
            max_keyframe_interval_sec=interval,
            reencoded=True,
            source_path=str(resolved_src),
            normalized_path=str(dest),
        )

    result = normalize_base_video_for_composition(resolved_src, dest, ffmpeg=ffmpeg)
    if result.get("code"):
        if dest.resolve() != resolved_src.resolve():
            dest.write_bytes(resolved_src.read_bytes())
        return dest, BaseVideoDiagnostics(
            max_keyframe_interval_sec=interval,
            reencoded=False,
            source_path=str(resolved_src),
            normalized_path=str(dest),
        )
    normalized_path = Path(str(result.get("path") or dest))
    post_interval = probe_keyframe_interval_sec(normalized_path, ffmpeg=ffmpeg)
    return normalized_path, BaseVideoDiagnostics(
        max_keyframe_interval_sec=post_interval or interval,
        reencoded=True,
        source_path=str(resolved_src),
        normalized_path=str(normalized_path),
    )
