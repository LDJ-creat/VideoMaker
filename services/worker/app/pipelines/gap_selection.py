from __future__ import annotations

from typing import Any

from app.runtime.video_gen_quota import VideoGenQuota

__all__ = [
    "VideoGenQuota",
    "select_provider",
    "select_provider_chain",
    "provider_rationale",
    "slot_needs_spoken_narration",
    "slot_needs_motion",
]

PACKAGING_ROLES = frozenset({"hook_text", "benefit_card", "comparison"})
VISUAL_ROLES = frozenset({"hook_visual", "product_closeup", "usage_scene"})
VO_KEYWORDS = ("voiceover", "narration", "narrated", "口播", "旁白", "解说", "配音", "spoken")


def slot_needs_spoken_narration(slot: dict[str, Any]) -> bool:
    script = str(slot.get("scriptIntent", "")).lower()
    return any(keyword in script for keyword in VO_KEYWORDS)


def slot_needs_motion(slot: dict[str, Any]) -> bool:
    required = slot.get("requiredAssetType") or []
    role = str(slot.get("role", ""))
    return role in VISUAL_ROLES and "video" in required


def select_provider(
    slot: dict[str, Any],
    *,
    weak_match: dict[str, Any] | None,
    quota: VideoGenQuota,
    variant_overrides: dict[str, Any] | None = None,
    impact: str = "medium",
) -> str:
    """Deterministic provider picker — master plan section 8.4."""
    if weak_match is not None and float(weak_match.get("matchScore", 0)) >= 0.38:
        return "asset_reuse"

    role = str(slot.get("role", ""))
    required = list(slot.get("requiredAssetType") or [])

    if role in PACKAGING_ROLES or "packaging" in required:
        return "hyperframes_material"

    if role in VISUAL_ROLES:
        overrides = variant_overrides or {}
        video_priority = str(overrides.get("videoGenPriority", "medium")).lower()
        prefer = list(overrides.get("preferProviders") or [])

        can_video = (
            quota.has_video_quota()
            and slot.get("importance") == "must_have"
            and impact == "high"
        )
        if can_video:
            if video_priority == "low" and "image_generation" in prefer:
                return "image_generation"
            return "video_generation"
        return "image_generation"

    if slot_needs_spoken_narration(slot):
        return "tts"

    return "hyperframes_material"


def select_provider_chain(
    slot: dict[str, Any],
    *,
    weak_match: dict[str, Any] | None,
    quota: VideoGenQuota,
    variant_overrides: dict[str, Any] | None = None,
    impact: str = "medium",
) -> list[str]:
    primary = select_provider(
        slot,
        weak_match=weak_match,
        quota=quota,
        variant_overrides=variant_overrides,
        impact=impact,
    )
    chain = [primary]
    if primary == "image_generation" and slot_needs_motion(slot):
        chain.append("hyperframes_material")
    return chain


def provider_rationale(provider: str, slot: dict[str, Any], *, weak_match: dict[str, Any] | None) -> str:
    role = str(slot.get("role", ""))
    if provider == "asset_reuse" and weak_match is not None:
        score = float(weak_match.get("matchScore", 0))
        return f"弱匹配分数 {score:.2f}，可通过裁剪/重排复用现有素材"
    if provider == "video_generation":
        return f"must_have 的 {role} 槽位影响高，使用一次 video_generation 配额"
    if provider == "image_generation":
        return f"{role} 槽位缺少写实画面，优先生成静态图像"
    if provider == "hyperframes_material":
        return f"{role} 槽位适合 HyperFrames 包装/动效卡片"
    if provider == "tts":
        return "scriptIntent 需要口播旁白"
    return f"为 {role} 槽位选择 {provider}"
