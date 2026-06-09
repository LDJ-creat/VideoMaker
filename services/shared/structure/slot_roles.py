"""Canonical VideoStructure slot role taxonomy (keep in sync with packages/contracts)."""

from __future__ import annotations

import re
from typing import Final

# Authoritative enum — matches video-structure.schema.json slot.role
SLOT_ROLE_ENUM: Final[tuple[str, ...]] = (
    "hook_visual",
    "hook_text",
    "product_closeup",
    "usage_scene",
    "benefit_card",
    "comparison",
    "proof",
    "transition",
    "cta",
)

SLOT_ROLES = frozenset(SLOT_ROLE_ENUM)

# HyperFrames / text-card slots (stock blocked; material templates)
PACKAGING_ROLES = frozenset(
    {
        "hook_text",
        "benefit_card",
        "comparison",
        "proof",
        "transition",
        "cta",
    }
)

# Gap planner: immediate hyperframes_material primary (proof uses visual/tts rules instead)
GAP_HYPERFRAMES_PRIMARY_ROLES = frozenset(
    {
        "hook_text",
        "benefit_card",
        "comparison",
        "transition",
        "cta",
    }
)

VISUAL_ROLES = frozenset(
    {
        "hook_visual",
        "product_closeup",
        "usage_scene",
    }
)

# After role normalization — eligible for generic Pexels B-roll
STOCK_GENERIC_VISUAL_ROLES = frozenset(
    {
        "hook_visual",
        "usage_scene",
    }
)

PRODUCT_CLOSEUP_ROLE = "product_closeup"

# Scheme 1: deprecated / alias values map into schema enum (no separate demonstration role)
SLOT_ROLE_ALIASES: dict[str, str] = {
    "demonstration": "usage_scene",
    "demo": "usage_scene",
    "tutorial": "usage_scene",
    "attention_grabber": "hook_visual",
    "intro": "hook_visual",
    "pain_point": "proof",
    "problem_visual": "proof",
    "problem": "proof",
    "product_intro": "product_closeup",
    "solution": "product_closeup",
    "benefit": "benefit_card",
    "call_to_action": "cta",
    "cta_visual": "cta",
    "hook": "hook_visual",
    "proof": "proof",
    "comparison": "comparison",
    "transition": "transition",
}

ROLE_GLOSSARY_ZH: dict[str, str] = {
    "hook_visual": "开场注意力画面，强调停滑与视觉冲击，不一定是产品本体",
    "hook_text": "开场/on-screen 文字包装（标题、悬念句、数字钩子）",
    "product_closeup": "特定主体/商品/SKU 特写，画面必须可识别该主体，禁止通用素材库替代",
    "usage_scene": "通用场景 B-roll、生活方式、操作演示、教程步骤（非 SKU 绑定）",
    "benefit_card": "卖点/利益点信息卡（文字 + 动效包装）",
    "comparison": "对比/前后/竞品对照信息卡",
    "proof": "证言、数据、案例或信任状（口播或包装卡）",
    "transition": "段间转场/过渡包装",
    "cta": "行动号召结尾包装",
}


def normalize_slot_role(role: str, *, default: str = "usage_scene") -> str:
    """Map LLM/coercer drift into schema slot.role enum."""
    raw = str(role or "").strip()
    if raw in SLOT_ROLES:
        return raw
    lowered = raw.lower()
    slug = re.sub(r"[^a-z0-9]+", "_", lowered).strip("_")
    compact = slug.replace("_", "")
    for key in (lowered, slug, compact):
        if not key:
            continue
        mapped = SLOT_ROLE_ALIASES.get(key)
        if mapped in SLOT_ROLES:
            return mapped
    fallback = default if default in SLOT_ROLES else "usage_scene"
    return fallback


def is_packaging_role(role: str) -> bool:
    return normalize_slot_role(role) in PACKAGING_ROLES


def is_visual_role(role: str) -> bool:
    return normalize_slot_role(role) in VISUAL_ROLES


def default_required_asset_types(role: str) -> list[str]:
    normalized = normalize_slot_role(role)
    if normalized in PACKAGING_ROLES:
        return ["text", "packaging"]
    return ["video", "image"]
