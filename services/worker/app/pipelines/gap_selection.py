from __future__ import annotations

from typing import Any

from app.runtime.asset_paths import resolve_match_asset_type
from app.runtime.video_gen_quota import VideoGenQuota
from app.stock.stock_eligibility import (
    completion_slot_for_stock,
    pexels_configured,
    stock_media_eligible,
)
from structure.slot_roles import GAP_HYPERFRAMES_PRIMARY_ROLES, VISUAL_ROLES

__all__ = [
    "VideoGenQuota",
    "select_provider",
    "select_provider_chain",
    "provider_rationale",
    "slot_needs_spoken_narration",
    "slot_needs_motion",
    "is_visual_slot",
    "WEAK_MATCH_THRESHOLD",
]

VO_KEYWORDS = ("voiceover", "narration", "narrated", "口播", "旁白", "解说", "配音", "spoken")
WEAK_MATCH_THRESHOLD = 0.38


def is_visual_slot(slot: dict[str, Any]) -> bool:
    return str(slot.get("role", "")) in VISUAL_ROLES


def slot_needs_spoken_narration(slot: dict[str, Any]) -> bool:
    script = str(slot.get("scriptIntent", "")).lower()
    return any(keyword in script for keyword in VO_KEYWORDS)


def slot_needs_motion(slot: dict[str, Any]) -> bool:
    required = slot.get("requiredAssetType") or []
    role = str(slot.get("role", ""))
    return role in VISUAL_ROLES and "video" in required


def _slot_id(slot: dict[str, Any]) -> str:
    return str(slot.get("id", ""))


def _prefer_provider_order(variant_overrides: dict[str, Any] | None) -> list[str]:
    overrides = variant_overrides or {}
    prefer = [str(p) for p in (overrides.get("preferProviders") or []) if str(p).strip()]
    if prefer:
        return prefer
    return [
        "asset_reuse",
        "stock_media_search",
        "hyperframes_material",
        "image_generation",
        "video_generation",
    ]


def _pick_primary_from_candidates(
    candidates: list[str],
    *,
    variant_overrides: dict[str, Any] | None,
) -> str:
    overrides = variant_overrides or {}
    if str(overrides.get("videoGenPriority", "")).lower() == "high":
        for preferred in ("video_generation", "image_generation"):
            if preferred in candidates:
                return preferred
    order = _prefer_provider_order(variant_overrides)
    for provider in order:
        if provider in candidates:
            return provider
    return candidates[0]


def _weak_match_score(weak_match: dict[str, Any] | None) -> float:
    if weak_match is None:
        return 0.0
    return float(weak_match.get("matchScore", 0))


def _prefer_image_over_video(variant_overrides: dict[str, Any] | None) -> bool:
    overrides = variant_overrides or {}
    video_priority = str(overrides.get("videoGenPriority", "medium")).lower()
    prefer = list(overrides.get("preferProviders") or [])
    return video_priority == "low" and "image_generation" in prefer


def _stock_media_priority(variant_overrides: dict[str, Any] | None) -> str:
    overrides = variant_overrides or {}
    return str(overrides.get("stockMediaPriority", "medium")).lower()


def _should_try_stock(
    slot: dict[str, Any],
    *,
    inventory: dict[str, Any] | None,
    variant_overrides: dict[str, Any] | None,
) -> bool:
    if not pexels_configured():
        return False
    if _stock_media_priority(variant_overrides) == "low":
        return False
    brief = (inventory or {}).get("userBrief") or {}
    brief_dict = brief if isinstance(brief, dict) else {}
    stock_slot = completion_slot_for_stock(slot, brief=brief_dict)
    eligible, _reason = stock_media_eligible(
        stock_slot,
        brief=brief_dict,
    )
    return eligible


def _aigc_visual_provider(
    slot: dict[str, Any],
    *,
    weak_match: dict[str, Any] | None,
    quota: VideoGenQuota,
    slot_id: str,
    variant_overrides: dict[str, Any] | None,
) -> str:
    score = _weak_match_score(weak_match)
    if score >= WEAK_MATCH_THRESHOLD and weak_match is not None:
        if quota.can_generate_for_slot(slot_id) and not _prefer_image_over_video(variant_overrides):
            return "video_generation"
        return "image_generation"
    if quota.can_generate_for_slot(slot_id) and not _prefer_image_over_video(variant_overrides):
        return "video_generation"
    return "image_generation"


def select_provider(
    slot: dict[str, Any],
    *,
    weak_match: dict[str, Any] | None,
    quota: VideoGenQuota,
    inventory: dict[str, Any] | None = None,
    variant_overrides: dict[str, Any] | None = None,
    impact: str = "medium",
) -> str:
    """Deterministic provider picker for gap completion actions."""
    inv = inventory or {}
    slot_id = _slot_id(slot)
    role = str(slot.get("role", ""))
    required = list(slot.get("requiredAssetType") or [])

    if role in GAP_HYPERFRAMES_PRIMARY_ROLES or "packaging" in required:
        return "hyperframes_material"

    score = _weak_match_score(weak_match)
    if score >= WEAK_MATCH_THRESHOLD and weak_match is not None:
        asset_type = resolve_match_asset_type(weak_match, inv)
        if asset_type == "video":
            return "asset_reuse"
        if asset_type == "image" and is_visual_slot(slot):
            if _should_try_stock(slot, inventory=inv, variant_overrides=variant_overrides):
                return "stock_media_search"
            return _aigc_visual_provider(
                slot,
                weak_match=weak_match,
                quota=quota,
                slot_id=slot_id,
                variant_overrides=variant_overrides,
            )

    if is_visual_slot(slot):
        candidates: list[str] = []
        if _should_try_stock(slot, inventory=inv, variant_overrides=variant_overrides):
            candidates.append("stock_media_search")
        candidates.append("hyperframes_material")
        if quota.can_generate_for_slot(slot_id) and not _prefer_image_over_video(variant_overrides):
            candidates.append("video_generation")
        candidates.append("image_generation")
        return _pick_primary_from_candidates(candidates, variant_overrides=variant_overrides)

    if slot_needs_spoken_narration(slot):
        return "tts"

    return "hyperframes_material"


def select_provider_chain(
    slot: dict[str, Any],
    *,
    weak_match: dict[str, Any] | None,
    quota: VideoGenQuota,
    inventory: dict[str, Any] | None = None,
    variant_overrides: dict[str, Any] | None = None,
    impact: str = "medium",
) -> list[str]:
    primary = select_provider(
        slot,
        weak_match=weak_match,
        quota=quota,
        inventory=inventory,
        variant_overrides=variant_overrides,
        impact=impact,
    )
    chain = [primary]
    if primary == "stock_media_search" and is_visual_slot(slot):
        chain.append("hyperframes_material")
    elif primary == "image_generation" and (slot_needs_motion(slot) or is_visual_slot(slot)):
        chain.append("hyperframes_material")
    elif primary == "asset_reuse" and is_visual_slot(slot):
        chain.append("hyperframes_material")
    return chain


def provider_rationale(provider: str, slot: dict[str, Any], *, weak_match: dict[str, Any] | None) -> str:
    role = str(slot.get("role", ""))
    if provider == "asset_reuse" and weak_match is not None:
        score = float(weak_match.get("matchScore", 0))
        return f"弱匹配分数 {score:.2f}，裁剪复用已有视频素材"
    if provider == "video_generation":
        if weak_match is not None and _weak_match_score(weak_match) >= WEAK_MATCH_THRESHOLD:
            return f"{role} 槽位对图片弱匹配，使用图生视频（i2v）补全分镜"
        return f"{role} 槽位使用文生视频（t2v）生成分镜片段"
    if provider == "stock_media_search":
        return f"{role} 槽位优先检索 Pexels 素材库（真实场景 B-roll）"
    if provider == "image_generation":
        return f"{role} 槽位缺少可用视频配额或需静态画面，优先生成图像"
    if provider == "hyperframes_material":
        return f"{role} 槽位适合 HyperFrames 包装/动效卡片"
    if provider == "tts":
        return "scriptIntent 需要口播旁白"
    return f"为 {role} 槽位选择 {provider}"
