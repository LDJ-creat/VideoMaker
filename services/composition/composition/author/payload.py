from __future__ import annotations

from typing import Any

from composition.aspect_ratio import render_dimensions
from composition.types import AuthorRequest

VIDEO_LINT_CHECKLIST: tuple[str, ...] = (
    'Every <video> must include a unique id attribute (e.g. id="base-video").',
    'Every <video> with src must include data-start="0" (or the intended in-point).',
    "When the clip should end before the source ends, also set data-duration to the slot duration.",
    "Keep the base video visible as the bottom layer; place overlays above it only.",
    "timelineScript must use the shell-provided tl — never declare const tl, let tl, or gsap.timeline().",
)


def has_video_asset_refs(asset_refs: list[dict[str, Any]] | None) -> bool:
    if not asset_refs:
        return False
    return any(str(ref.get("type", "")).strip().lower() == "video" for ref in asset_refs if isinstance(ref, dict))


def build_material_author_user_payload(request: AuthorRequest) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "slot": request.slot,
        "brandColors": request.brand_colors,
        "variantOverrides": request.variant_overrides,
        "assetRefs": request.asset_refs,
        "validationErrors": request.validation_errors,
    }
    if isinstance(request.finish_brief, dict):
        payload["finishBrief"] = request.finish_brief
    if (
        isinstance(request.visual_style_bible, dict)
        and request.visual_style_bible.get("summary")
    ):
        payload["visualStyleBible"] = request.visual_style_bible
    if has_video_asset_refs(request.asset_refs):
        payload["videoLintChecklist"] = list(VIDEO_LINT_CHECKLIST)
    width, height = render_dimensions(request.aspect_ratio)
    payload["renderTarget"] = {
        "aspectRatio": request.aspect_ratio,
        "width": width,
        "height": height,
    }
    if isinstance(request.slot_timing, dict) and request.slot_timing:
        payload["slotTiming"] = request.slot_timing
    return payload
