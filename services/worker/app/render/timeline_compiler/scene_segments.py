from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

MediaKind = Literal["video", "image", "placeholder"]

_IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp")
_VIDEO_SUFFIXES = (".mp4", ".webm", ".mov", ".mkv")


@dataclass(slots=True)
class SceneSegment:
    clip_id: str
    start_sec: float
    end_sec: float
    source_ref: str | None
    media_kind: MediaKind

    @property
    def duration_sec(self) -> float:
        return max(0.1, float(self.end_sec) - float(self.start_sec))


def _is_image_ref(source_ref: str) -> bool:
    return source_ref.lower().endswith(_IMAGE_SUFFIXES)


def _is_video_ref(source_ref: str) -> bool:
    return source_ref.lower().endswith(_VIDEO_SUFFIXES)


def _resolve_source_path(render_root: Path, source_ref: str | None) -> Path | None:
    if not source_ref:
        return None
    candidate = (render_root / source_ref).resolve()
    if candidate.is_file():
        return candidate
    path = Path(source_ref)
    if path.is_file():
        return path
    return None


def _media_kind_for_clip(clip: dict[str, Any], track_type: str) -> MediaKind:
    source_ref = str(clip.get("sourceRef", "")).strip()
    if source_ref:
        if _is_video_ref(source_ref) or track_type == "video":
            return "video"
        if _is_image_ref(source_ref) or track_type == "image":
            return "image"
    if track_type == "image":
        return "image"
    if track_type == "video":
        return "video"
    return "placeholder"


def extract_scene_segments(
    timeline: dict[str, Any],
    *,
    render_root: Path,
) -> list[SceneSegment]:
    tracks = timeline.get("tracks", [])
    if not isinstance(tracks, list):
        return []

    by_id: dict[str, SceneSegment] = {}
    track_priority = {"video": 0, "image": 1}

    for track in tracks:
        if not isinstance(track, dict):
            continue
        track_type = str(track.get("type", ""))
        if track_type not in track_priority:
            continue
        for clip in track.get("clips", []):
            if not isinstance(clip, dict):
                continue
            clip_id = str(clip.get("id", "")).strip()
            if not clip_id:
                continue
            segment = SceneSegment(
                clip_id=clip_id,
                start_sec=float(clip.get("startSec", 0.0)),
                end_sec=float(clip.get("endSec", 0.0)),
                source_ref=str(clip.get("sourceRef", "")).strip() or None,
                media_kind=_media_kind_for_clip(clip, track_type),
            )
            existing = by_id.get(clip_id)
            if existing is None:
                by_id[clip_id] = segment
                continue
            if track_priority[track_type] < track_priority.get(
                "video" if existing.media_kind == "video" else "image",
                9,
            ):
                by_id[clip_id] = segment

    segments = sorted(by_id.values(), key=lambda item: (item.start_sec, item.clip_id))
    return segments


def resolve_segment_media_path(render_root: Path, segment: SceneSegment) -> Path | None:
    return _resolve_source_path(render_root, segment.source_ref)
