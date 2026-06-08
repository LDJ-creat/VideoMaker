from __future__ import annotations



import os

import re

from typing import Any



PRODUCT_CLOSEUP_ROLE = "product_closeup"

DEMONSTRATION_ROLE = "demonstration"

PRODUCT_BOUND_MARKERS = ("本品", "我们的", "our product", "this product", "sku")

PACKAGING_ROLES = frozenset({"hook_text", "benefit_card", "comparison"})

VISUAL_ROLES = frozenset(

    {"hook_visual", "product_closeup", "usage_scene", DEMONSTRATION_ROLE}

)





def _brief_dict(inventory: dict[str, Any] | None) -> dict[str, Any]:

    if not inventory:

        return {}

    brief = inventory.get("userBrief")

    return brief if isinstance(brief, dict) else {}





def _product_terms(brief: dict[str, Any]) -> list[str]:

    terms: list[str] = []

    for key in ("productName", "subjectName"):

        value = str(brief.get(key, "")).strip()

        if value:

            terms.append(value.lower())

    for point in brief.get("sellingPoints") or []:

        text = str(point).strip()

        if text:

            terms.append(text.lower())

    return terms





def is_product_bound_brief(brief: dict[str, Any] | None) -> bool:
    """Only commerce-category briefs keep strict product_closeup stock blocking."""
    brief_dict = brief or {}
    category = str(brief_dict.get("contentCategory", "general")).strip().lower()
    if category != "product_commerce":
        return False
    return bool(_product_terms(brief_dict))





def normalize_completion_slot_role(

    slot: dict[str, Any],

    *,

    brief: dict[str, Any] | None = None,

) -> str:

    """Map product_closeup to usage_scene for non-product briefs during gap/stock completion."""

    role = str(slot.get("role", ""))

    if role in {PRODUCT_CLOSEUP_ROLE, DEMONSTRATION_ROLE} and not is_product_bound_brief(brief):

        return "usage_scene"

    if role == DEMONSTRATION_ROLE:

        return "usage_scene"

    return role





def completion_slot_for_stock(

    slot: dict[str, Any],

    *,

    brief: dict[str, Any] | None = None,

) -> dict[str, Any]:

    normalized_role = normalize_completion_slot_role(slot, brief=brief)

    if normalized_role == str(slot.get("role", "")):

        return slot

    return {**slot, "role": normalized_role}





def _text_contains_product_binding(text: str, product_terms: list[str]) -> bool:

    lowered = text.lower()

    if any(marker in lowered for marker in PRODUCT_BOUND_MARKERS):

        return True

    return any(term and term in lowered for term in product_terms)





def stock_media_eligible(

    slot: dict[str, Any],

    *,

    brief: dict[str, Any] | None = None,

) -> tuple[bool, str]:

    """Return whether a slot may use Pexels stock search and a reason code."""

    brief_dict = brief or {}

    slot = completion_slot_for_stock(slot, brief=brief_dict)

    role = str(slot.get("role", ""))

    if role in PACKAGING_ROLES:

        return False, "packaging_role"

    if role == PRODUCT_CLOSEUP_ROLE:

        return False, "product_closeup"

    required = list(slot.get("requiredAssetType") or [])

    if "packaging" in required:

        return False, "packaging_required"



    product_terms = _product_terms(brief_dict)

    script_intent = str(slot.get("scriptIntent", ""))

    if _text_contains_product_binding(script_intent, product_terms):

        return False, "product_bound"



    if role in {"usage_scene", "hook_visual", DEMONSTRATION_ROLE}:

        return True, "generic_visual"

    if "video" in required or "image" in required:

        return True, "visual_asset_gap"

    return False, "non_visual"





def slot_needs_motion_local(slot: dict[str, Any]) -> bool:

    required = slot.get("requiredAssetType") or []

    role = str(slot.get("role", ""))

    return role in VISUAL_ROLES and "video" in required





def stock_search_preferences(
    slot: dict[str, Any],
    *,
    scene: dict[str, Any] | None = None,
    brief: dict[str, Any] | None = None,
    aspect_ratio: str | None = None,
) -> dict[str, Any]:
    from app.render.aspect_ratio import pexels_orientation, resolve_aspect_ratio

    slot = completion_slot_for_stock(slot, brief=brief)
    prefer_video = slot_needs_motion_local(slot) or str(slot.get("role", "")) == "usage_scene"

    orientation: str | None = None
    if aspect_ratio:
        orientation = pexels_orientation(aspect_ratio)
    elif isinstance(brief, dict) and brief.get("aspectRatio"):
        target = float((brief.get("durationTarget") or {}).get("targetSec") or 60.0)
        orientation = pexels_orientation(resolve_aspect_ratio(brief, target_sec=target))
    elif scene:
        visual = str(scene.get("visual", "")).lower()
        if any(token in visual for token in ("vertical", "portrait", "竖屏", "9:16")):
            orientation = "portrait"
        elif any(token in visual for token in ("square", "1:1")):
            orientation = "square"
        elif any(token in visual for token in ("landscape", "横屏", "16:9")):
            orientation = "landscape"

    return {"preferVideo": prefer_video, "orientation": orientation}





def pexels_configured() -> bool:

    if os.getenv("VIDEOMAKER_STOCK_MEDIA_ENABLED", "true").strip().lower() in {

        "0",

        "false",

        "no",

    }:

        return False

    return bool(os.getenv("VIDEOMAKER_PEXELS_API_KEY", "").strip())





def stock_match_min_score() -> float:

    raw = os.getenv("VIDEOMAKER_STOCK_MATCH_MIN_SCORE", "0.55").strip()

    try:

        return float(raw)

    except ValueError:

        return 0.55





def stock_max_candidates() -> int:

    raw = os.getenv("VIDEOMAKER_STOCK_MAX_CANDIDATES", "5").strip()

    try:

        return max(1, int(raw))

    except ValueError:

        return 5





def normalize_query_tokens(text: str) -> set[str]:

    if not text:

        return set()

    parts = re.findall(r"[a-zA-Z0-9]+", text.lower())

    return {part for part in parts if len(part) > 2}

