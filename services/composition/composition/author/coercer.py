from __future__ import annotations

import html
from typing import Any

from composition.author.payload import has_video_asset_refs

_ROLE_DEFAULT_TEMPLATE: dict[str, str] = {
    "benefit_card": "benefit-card",
    "comparison": "benefit-card",
    "proof": "benefit-card",
    "transition": "benefit-card",
    "cta": "benefit-card",
    "hook_text": "title-lower-third",
    "hook_visual": "ken-burns",
    "product_closeup": "ken-burns",
    "usage_scene": "ken-burns",
}

_WORDLESS_LOWER_THIRD = (
    '<div class="lower-third-bar absolute inset-x-[8%] bottom-[12%] h-1 '
    'rounded-full bg-white/35"></div>'
)


def _first_video_ref(asset_refs: list[dict[str, Any]]) -> dict[str, Any] | None:
    for ref in asset_refs:
        if not isinstance(ref, dict):
            continue
        if str(ref.get("type", "")).strip().lower() == "video":
            return ref
    return None


def _image_asset_refs(asset_refs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for ref in asset_refs:
        if not isinstance(ref, dict):
            continue
        asset_type = str(ref.get("type", "")).strip().lower()
        if asset_type in {"", "image"}:
            refs.append(ref)
    return refs


def build_video_composition_fallback(
    slot: dict[str, Any],
    asset_refs: list[dict[str, Any]],
    *,
    duration_sec: float = 3.0,
) -> dict[str, Any]:
    video_ref = _first_video_ref(asset_refs)
    if video_ref is None:
        raise ValueError("video composition fallback requires a video asset ref")
    uri = str(video_ref.get("uri", "")).strip()
    if not uri:
        raise ValueError("video asset ref missing uri")

    duration = max(0.5, min(30.0, float(duration_sec)))
    timeline_script = (
        "tl.set('[data-composition-id=\"main\"]', { autoAlpha: 1 }, 0);"
        "tl.from('.lower-third-bar', { scaleX: 0, transformOrigin: 'left center', "
        "duration: 0.45, ease: 'power2.out' }, 0.2);"
    )

    body_html = (
        '<div data-composition-id="main" class="relative h-full w-full overflow-hidden">'
        f'<video id="base-video" class="absolute inset-0 h-full w-full object-cover" '
        f'src="{html.escape(uri, quote=True)}" data-start="0" data-duration="{duration:g}" '
        f'muted playsinline></video>'
        f"{_WORDLESS_LOWER_THIRD}"
        "</div>"
    )
    return {
        "template": "composition",
        "durationSec": duration,
        "composition": {
            "bodyHtml": body_html,
            "styles": ".lower-third-bar { will-change: transform; }",
            "timelineScript": timeline_script,
            "registryBlocks": [],
        },
    }


def fallback_legacy_spec(slot: dict[str, Any], *, duration_sec: float = 3.0) -> dict[str, Any]:
    role = str(slot.get("role", "")).strip()
    template = _ROLE_DEFAULT_TEMPLATE.get(role, "benefit-card")
    return {
        "template": template,
        "durationSec": max(0.5, min(30.0, float(duration_sec))),
        "params": {},
    }


def build_author_fallback_spec(
    slot: dict[str, Any],
    *,
    asset_refs: list[dict[str, Any]] | None = None,
    duration_sec: float = 3.0,
) -> dict[str, Any]:
    refs = [ref for ref in (asset_refs or []) if isinstance(ref, dict)]
    if has_video_asset_refs(refs):
        return build_video_composition_fallback(slot, refs, duration_sec=duration_sec)
    image_refs = _image_asset_refs(refs)
    if image_refs:
        return {
            "template": "ken-burns",
            "durationSec": max(0.5, min(30.0, float(duration_sec))),
            "params": {"assetRefs": image_refs},
        }
    legacy = fallback_legacy_spec(slot, duration_sec=duration_sec)
    if legacy.get("template") == "ken-burns":
        return fallback_legacy_spec(
            {**slot, "role": "hook_text" if slot.get("role") == "hook_visual" else "benefit_card"},
            duration_sec=duration_sec,
        )
    return legacy
