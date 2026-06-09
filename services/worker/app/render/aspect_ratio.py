from __future__ import annotations

from typing import Any

AspectRatio = str

VALID_ASPECT_RATIOS = frozenset({"9:16", "16:9", "1:1"})
DEFAULT_ASPECT_RATIO: AspectRatio = "9:16"


def resolve_aspect_ratio(
    brief: dict[str, Any] | None,
    *,
    plan: dict[str, Any] | None = None,
    target_sec: float | None = None,
) -> AspectRatio:
    del target_sec  # kept for call-site compatibility; aspect ratio follows brief only
    if isinstance(plan, dict):
        plan_ratio = plan.get("aspectRatio")
        if isinstance(plan_ratio, str) and plan_ratio in VALID_ASPECT_RATIOS:
            return plan_ratio
    raw = (brief or {}).get("aspectRatio")
    if isinstance(raw, str) and raw in VALID_ASPECT_RATIOS:
        return raw
    return DEFAULT_ASPECT_RATIO


def render_dimensions(aspect_ratio: AspectRatio) -> tuple[int, int]:
    if aspect_ratio == "16:9":
        return 1920, 1080
    if aspect_ratio == "1:1":
        return 1080, 1080
    return 1080, 1920


def pexels_orientation(aspect_ratio: AspectRatio) -> str:
    return {
        "9:16": "portrait",
        "16:9": "landscape",
        "1:1": "square",
    }[aspect_ratio]


def subtitle_layout(aspect_ratio: AspectRatio) -> dict[str, int]:
    if aspect_ratio == "16:9":
        return {
            "fontSizePx": 42,
            "bottomPaddingPx": 72,
            "sidePaddingPx": 96,
            "backdropHeightPx": 88,
        }
    if aspect_ratio == "1:1":
        return {
            "fontSizePx": 36,
            "bottomPaddingPx": 88,
            "sidePaddingPx": 56,
            "backdropHeightPx": 80,
        }
    return {
        "fontSizePx": 38,
        "bottomPaddingPx": 120,
        "sidePaddingPx": 48,
        "backdropHeightPx": 72,
    }
