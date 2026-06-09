from __future__ import annotations

import re
from typing import Any

_VALID_TEMPLATES = frozenset({"benefit-card", "title-lower-third", "ken-burns", "custom", "composition"})
_ALLOWED_PARAM_KEYS = frozenset({"title", "bullets", "colors", "assetRefs", "subtitle"})

_TEMPLATE_ALIASES: dict[str, str] = {
    "benefit-card": "benefit-card",
    "benefit_card": "benefit-card",
    "benefitcard": "benefit-card",
    "comparison-card": "benefit-card",
    "comparison_card": "benefit-card",
    "comparison": "benefit-card",
    "proof-card": "benefit-card",
    "proof_card": "benefit-card",
    "title-lower-third": "title-lower-third",
    "title_lower_third": "title-lower-third",
    "lower-third": "title-lower-third",
    "lower_third": "title-lower-third",
    "lowerthird": "title-lower-third",
    "hook-text": "title-lower-third",
    "hook_text": "title-lower-third",
    "ken-burns": "ken-burns",
    "ken_burns": "ken-burns",
    "kenburns": "ken-burns",
    "custom": "custom",
    "composition": "composition",
}

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

_PACKAGING_ROLES = frozenset(
    {"benefit_card", "comparison", "proof", "transition", "cta", "hook_text"}
)

_COLOR_PARAM_KEYS: dict[str, str] = {
    "primary": "primary",
    "primarycolor": "primary",
    "primary_color": "primary",
    "background": "background",
    "backgroundcolor": "background",
    "background_color": "background",
    "text": "text",
    "textcolor": "text",
    "text_color": "text",
    "accent": "accent",
    "accentcolor": "accent",
    "accent_color": "accent",
}


def _normalize_template_key(value: str) -> str:
    lowered = value.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "_", lowered).strip("_")
    compact = slug.replace("_", "")
    return _TEMPLATE_ALIASES.get(lowered) or _TEMPLATE_ALIASES.get(slug) or _TEMPLATE_ALIASES.get(compact) or ""


def _template_without_image_assets(*, slot: dict[str, Any] | None) -> str:
    role = str((slot or {}).get("role", "")).strip()
    if role == "hook_text":
        return "title-lower-third"
    if role in _PACKAGING_ROLES:
        return "benefit-card"
    return "benefit-card"


def _resolve_template(payload: dict[str, Any], *, slot: dict[str, Any] | None) -> str:
    for key in ("template", "templateId", "templateName"):
        raw = payload.get(key)
        if isinstance(raw, str) and raw.strip():
            resolved = _normalize_template_key(raw)
            if resolved:
                return resolved
    role = str((slot or {}).get("role", "")).strip()
    return _ROLE_DEFAULT_TEMPLATE.get(role, "benefit-card")


def _coerce_duration(value: Any, *, template: str) -> float:
    try:
        duration = float(value)
    except (TypeError, ValueError):
        duration = 4.0 if template == "ken-burns" else 3.0
    return max(0.5, min(30.0, duration))


def _coerce_bullets(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _coerce_colors(params: dict[str, Any]) -> dict[str, Any]:
    colors = dict(params.get("colors") or {}) if isinstance(params.get("colors"), dict) else {}
    for key, raw in list(params.items()):
        normalized = key.strip().lower().replace("-", "")
        mapped = _COLOR_PARAM_KEYS.get(normalized)
        if mapped and isinstance(raw, str) and raw.strip():
            colors[mapped] = raw.strip()
    return colors


def _normalize_asset_ref(item: dict[str, Any]) -> dict[str, Any] | None:
    uri = str(item.get("uri", "")).strip()
    if not uri:
        return None
    ref = dict(item)
    ref["uri"] = uri
    ref["type"] = str(ref.get("type") or "image")
    ref["id"] = str(ref.get("id") or f"material-ref-{abs(hash(uri))}")
    ref["createdAt"] = str(ref.get("createdAt") or "1970-01-01T00:00:00Z")
    return ref


def _coerce_asset_refs(
    *,
    params: dict[str, Any],
    payload: dict[str, Any],
    asset_refs: list[dict[str, Any]] | None,
) -> list[dict[str, Any]] | None:
    refs: list[dict[str, Any]] = []
    seen_uris: set[str] = set()
    for source in (params.get("assetRefs"), payload.get("assetRefs"), asset_refs):
        if not isinstance(source, list):
            continue
        for item in source:
            if not isinstance(item, dict):
                continue
            normalized = _normalize_asset_ref(item)
            if normalized is None or normalized["uri"] in seen_uris:
                continue
            seen_uris.add(normalized["uri"])
            refs.append(normalized)
    return refs or None


def coerce_material_spec_output(
    payload: dict[str, Any],
    *,
    slot: dict[str, Any] | None = None,
    asset_refs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Normalize common LLM drift into a MaterialSpec-shaped dict."""
    composition = payload.get("composition")
    if isinstance(composition, dict) or _resolve_template(payload, slot=slot) == "composition":
        body_html = ""
        if isinstance(composition, dict):
            body_html = str(composition.get("bodyHtml", "")).strip()
        if body_html:
            coerced_composition: dict[str, Any] = {"bodyHtml": body_html}
            for key in ("styles", "timelineScript", "registryBlocks"):
                if isinstance(composition, dict) and composition.get(key) is not None:
                    coerced_composition[key] = composition[key]
            return {
                "template": "composition",
                "durationSec": _coerce_duration(payload.get("durationSec"), template="composition"),
                "composition": coerced_composition,
            }

    raw_params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
    params = dict(raw_params)
    template = _resolve_template(payload, slot=slot)

    title = str(params.get("title") or payload.get("title") or "").strip()
    subtitle = str(params.get("subtitle") or payload.get("subtitle") or "").strip()
    bullets = _coerce_bullets(params.get("bullets") or payload.get("bullets"))
    colors = _coerce_colors(params)
    coerced_asset_refs = _coerce_asset_refs(params=params, payload=payload, asset_refs=asset_refs)

    coerced_params: dict[str, Any] = {}
    if title:
        coerced_params["title"] = title
    if subtitle:
        coerced_params["subtitle"] = subtitle
    if bullets:
        coerced_params["bullets"] = bullets
    if colors:
        coerced_params["colors"] = colors
    if coerced_asset_refs:
        coerced_params["assetRefs"] = coerced_asset_refs

    if not coerced_params.get("title"):
        script_intent = str((slot or {}).get("scriptIntent", "")).strip()
        if script_intent:
            coerced_params["title"] = script_intent[:120]
    if template == "benefit-card" and not coerced_params.get("bullets"):
        visual_intent = str((slot or {}).get("visualIntent", "")).strip()
        if visual_intent:
            coerced_params["bullets"] = [visual_intent[:160]]

    if not coerced_params:
        coerced_params["title"] = str((slot or {}).get("visualIntent") or "VideoMaker").strip()[:120]

    if template == "ken-burns" and not coerced_asset_refs:
        template = _template_without_image_assets(slot=slot)
        if template == "benefit-card" and not coerced_params.get("bullets"):
            visual_intent = str((slot or {}).get("visualIntent", "")).strip()
            if visual_intent:
                coerced_params["bullets"] = [visual_intent[:160]]

    resolved_template = template if template in _VALID_TEMPLATES else "benefit-card"
    return {
        "template": resolved_template,
        "durationSec": _coerce_duration(payload.get("durationSec"), template=resolved_template),
        "params": coerced_params,
    }


def build_ken_burns_spec(
    asset_refs: list[dict[str, Any]],
    *,
    duration_sec: float = 4.0,
) -> dict[str, Any]:
    refs = _coerce_asset_refs(params={}, payload={}, asset_refs=asset_refs)
    if not refs:
        raise ValueError("ken-burns spec requires at least one asset ref")
    return {
        "template": "ken-burns",
        "durationSec": _coerce_duration(duration_sec, template="ken-burns"),
        "params": {"assetRefs": refs},
    }
