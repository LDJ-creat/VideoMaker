from __future__ import annotations

import os
from typing import Literal

TransitionMode = Literal["cut", "overlay_fade", "xfade"]

_FADE_MAP = {
    "fade": "fade",
    "quick-cut": "fade",
    "wipe": "wiperight",
    "cut": "fade",
}


def resolve_transition_mode() -> TransitionMode:
    env = os.getenv("VIDEOMAKER_FFMPEG_TRANSITION_MODE", "cut").strip().lower()
    if env in {"cut", "overlay_fade", "xfade"}:
        return env  # type: ignore[return-value]
    return "cut"


def transition_duration_sec(content: str, *, mode: TransitionMode) -> float:
    if mode == "cut":
        return 0.0
    normalized = str(content or "fade").strip().lower()
    if normalized in {"cut", "quick-cut"}:
        return 0.0
    return 0.3


def xfade_transition_name(content: str) -> str:
    normalized = str(content or "fade").strip().lower()
    return _FADE_MAP.get(normalized, "fade")


def transition_content_at_boundary(
    transition_clips: list[dict],
    boundary_sec: float,
) -> str:
    """Pick transition clip content active at a scene boundary timestamp."""
    if not transition_clips:
        return "quick-cut"
    tolerance = 0.05
    for clip in transition_clips:
        start = float(clip.get("startSec", 0.0))
        end = float(clip.get("endSec", start))
        if start - tolerance <= boundary_sec <= end + tolerance:
            return str(clip.get("content", "fade")).strip().lower() or "fade"
    nearest = min(
        transition_clips,
        key=lambda clip: abs(
            float(clip.get("startSec", 0.0)) - boundary_sec
        ),
    )
    return str(nearest.get("content", "quick-cut")).strip().lower() or "quick-cut"
