from __future__ import annotations

from pathlib import Path
from typing import Any

from app.pipelines.tts_mode import VO_MASTER_CLIP_ID, is_global_tts_mode
from app.render.timeline_compiler.scene_segments import SceneSegment

AudioSpec = tuple[Path, float, float, float]


def resolve_render_fps() -> int:
    import os

    try:
        return max(1, int(os.getenv("VIDEOMAKER_FFMPEG_RENDER_FPS", "30")))
    except ValueError:
        return 30


def resolve_video_crf() -> int:
    import os

    try:
        return max(0, min(51, int(os.getenv("VIDEOMAKER_FFMPEG_VIDEO_CRF", "23"))))
    except ValueError:
        return 23


def resolve_bgm_volume() -> float:
    import os

    try:
        return max(0.0, min(1.0, float(os.getenv("VIDEOMAKER_FFMPEG_BGM_VOLUME", "0.25"))))
    except ValueError:
        return 0.25


def _resolve_media_path(render_root: Path, source_ref: str) -> Path | None:
    if not source_ref:
        return None
    candidate = (render_root / source_ref).resolve()
    if candidate.is_file():
        return candidate
    alt = Path(source_ref)
    if alt.is_file():
        return alt.resolve()
    return None


def collect_bgm_specs(
    timeline: dict[str, Any],
    *,
    render_root: Path,
    volume: float,
) -> list[AudioSpec]:
    tracks = timeline.get("tracks", [])
    if not isinstance(tracks, list):
        return []
    specs: list[AudioSpec] = []
    for track in tracks:
        if not isinstance(track, dict) or track.get("type") != "bgm":
            continue
        for clip in track.get("clips", []):
            if not isinstance(clip, dict):
                continue
            source_ref = str(clip.get("sourceRef", "")).strip()
            path = _resolve_media_path(render_root, source_ref)
            if path is None:
                continue
            specs.append(
                (
                    path,
                    float(clip.get("startSec", 0.0)),
                    float(clip.get("endSec", 0.0)),
                    volume,
                )
            )
    return specs


def _voiceover_clips(timeline: dict[str, Any]) -> list[dict[str, Any]]:
    tracks = timeline.get("tracks", [])
    if not isinstance(tracks, list):
        return []
    for track in tracks:
        if isinstance(track, dict) and track.get("type") == "voiceover":
            clips = [clip for clip in track.get("clips", []) if isinstance(clip, dict)]
            return sorted(clips, key=lambda clip: float(clip.get("startSec", 0.0)))
    return []


def collect_voiceover_specs(
    timeline: dict[str, Any],
    *,
    render_root: Path,
    target_duration_sec: float,
    tts_mode: str | None = None,
) -> list[AudioSpec]:
    """Build voiceover mix specs: one global master or per-scene clips with timeline windows."""
    clips = _voiceover_clips(timeline)
    if not clips:
        fallback = render_root / "materials" / "master.wav"
        if fallback.is_file():
            return [(fallback.resolve(), 0.0, target_duration_sec, 1.0)]
        return []

    global_mode = is_global_tts_mode(tts_mode or "")
    if global_mode or (
        len(clips) == 1 and str(clips[0].get("id", "")) == VO_MASTER_CLIP_ID
    ):
        source_ref = str(clips[0].get("sourceRef", "")).strip()
        path = _resolve_media_path(render_root, source_ref)
        if path is None:
            fallback = render_root / "materials" / "master.wav"
            if fallback.is_file():
                path = fallback.resolve()
        if path is not None:
            end_sec = float(clips[0].get("endSec", target_duration_sec))
            return [(path, 0.0, max(end_sec, target_duration_sec), 1.0)]
        return []

    specs: list[AudioSpec] = []
    for clip in clips:
        source_ref = str(clip.get("sourceRef", "")).strip()
        if not source_ref:
            continue
        path = _resolve_media_path(render_root, source_ref)
        if path is None:
            continue
        start_sec = float(clip.get("startSec", 0.0))
        end_sec = float(clip.get("endSec", start_sec))
        if end_sec <= start_sec:
            continue
        specs.append((path, start_sec, end_sec, 1.0))
    return specs


def segments_total_duration(segments: list[SceneSegment]) -> float:
    if not segments:
        return 0.0
    return max(segment.end_sec for segment in segments)
