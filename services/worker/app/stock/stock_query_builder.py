from __future__ import annotations

import re
from typing import Any

from app.stock.stock_eligibility import (
    _product_terms,
    completion_slot_for_stock,
    stock_search_preferences,
)


def _scene_for_slot(slot_id: str, storyboard: list[dict[str, Any]]) -> dict[str, Any] | None:
    for scene in storyboard:
        if scene.get("slotId") == slot_id:
            return scene
    return None


def _strip_product_terms(text: str, product_terms: list[str]) -> str:
    cleaned = text
    for term in product_terms:
        if not term:
            continue
        cleaned = re.sub(re.escape(term), " ", cleaned, flags=re.IGNORECASE)
    return cleaned


def _tokenize(text: str) -> list[str]:
    parts = re.findall(r"[\u4e00-\u9fff]+|[a-zA-Z0-9]+", text.lower())
    return [part for part in parts if len(part) > 1]


def build_deterministic_stock_query(
    *,
    slot: dict[str, Any],
    storyboard: list[dict[str, Any]],
    gap_reason: str = "",
    brief: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Fallback query builder when LLM stock_query_author is unavailable."""
    slot_id = str(slot.get("id", ""))
    scene = _scene_for_slot(slot_id, storyboard) or {}
    brief_dict = brief or {}
    product_terms = _product_terms(brief_dict)

    visual = _strip_product_terms(str(scene.get("visual", "")), product_terms)
    script = _strip_product_terms(str(scene.get("script", "")), product_terms)
    intent = _strip_product_terms(str(slot.get("scriptIntent", "")), product_terms)
    reason = _strip_product_terms(gap_reason, product_terms)

    stock_slot = completion_slot_for_stock(slot, brief=brief_dict)
    role = str(stock_slot.get("role", ""))
    role_hint = {
        "usage_scene": "lifestyle usage scene tutorial demonstration",
        "hook_visual": "attention grabbing visual hook",
        "product_closeup": "product close up",
    }.get(role, "b-roll footage")

    parts = [role_hint, visual, intent, script, reason, str(brief_dict.get("topic", ""))]
    tokens = _tokenize(" ".join(parts))
    deduped: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        if token in seen:
            continue
        seen.add(token)
        deduped.append(token)

    primary = " ".join(deduped[:8]).strip() or role_hint
    fallback = " ".join(deduped[4:12]).strip() or f"{role_hint} background"
    prefs = stock_search_preferences(slot, scene=scene, brief=brief_dict)
    return {
        "primaryQuery": primary,
        "fallbackQueries": [fallback] if fallback and fallback != primary else [],
        "locale": "en",
        "negativeTerms": ["logo", "brand", "watermark"],
        **prefs,
    }
