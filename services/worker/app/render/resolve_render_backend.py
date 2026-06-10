from __future__ import annotations

import os
from typing import Any, Literal

RenderBackendKind = Literal["ffmpeg", "hyperframes"]

_SUBTITLE_ID_PREFIX = "subtitle-"
_OVERLAY_ID_PREFIX = "overlay-"


def timeline_requires_live_html(timeline: dict[str, Any]) -> bool:
    """Return True when timeline needs HyperFrames final render (FFmpeg v1 gaps)."""
    if str(timeline.get("renderMode") or "").strip().lower() == "hyperframes":
        return True

    tracks = timeline.get("tracks", [])
    if not isinstance(tracks, list):
        return False

    for track in tracks:
        if not isinstance(track, dict):
            continue
        track_type = str(track.get("type", ""))
        clips = track.get("clips", [])
        if not isinstance(clips, list):
            continue

        if track_type == "effect":
            for clip in clips:
                if isinstance(clip, dict) and str(clip.get("id", "")).strip():
                    return True

        if track_type == "text":
            for clip in clips:
                if not isinstance(clip, dict):
                    continue
                clip_id = str(clip.get("id", ""))
                style_ref = str(clip.get("styleRef", ""))
                if clip_id.startswith(_SUBTITLE_ID_PREFIX):
                    continue
                if clip_id.startswith(_OVERLAY_ID_PREFIX):
                    continue
                if style_ref.startswith("style://packaging/"):
                    return True

    return False


def resolve_render_backend(
    timeline: dict[str, Any],
    *,
    plan: dict[str, Any] | None = None,
) -> RenderBackendKind:
    env = os.getenv("VIDEOMAKER_RENDER_BACKEND", "").strip().lower()
    if env == "hyperframes":
        return "hyperframes"
    if env == "ffmpeg":
        return "ffmpeg"

    merged = dict(timeline)
    if isinstance(plan, dict) and str(plan.get("renderMode") or "").strip():
        merged["renderMode"] = plan["renderMode"]

    if timeline_requires_live_html(merged):
        return "hyperframes"
    return "ffmpeg"


def build_render_backend(
    timeline: dict[str, Any],
    *,
    plan: dict[str, Any] | None = None,
    hyperframes_tool: Any | None = None,
    ffmpeg_tool: Any | None = None,
):
    from app.render.ffmpeg_backend import FfmpegRenderBackend
    from app.render.hyperframes_backend import HyperFramesRenderBackend

    if resolve_render_backend(timeline, plan=plan) == "hyperframes":
        return HyperFramesRenderBackend(tool=hyperframes_tool)
    return FfmpegRenderBackend(tool=ffmpeg_tool)
