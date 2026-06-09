"""LLM-proposed gap completion chains reconciled against hard rules and cost policy."""

from __future__ import annotations

from typing import Any

from app.pipelines.gap_selection import select_provider_chain
from app.runtime.asset_paths import resolve_match_asset_type
from app.runtime.video_gen_quota import VideoGenQuota
from app.stock.stock_eligibility import is_product_bound_brief
from structure.slot_roles import (
    GAP_HYPERFRAMES_PRIMARY_ROLES,
    PRODUCT_CLOSEUP_ROLE,
    normalize_slot_role,
)

MATERIAL_PROVIDERS = frozenset(
    {
        "asset_reuse",
        "stock_media_search",
        "image_generation",
        "video_generation",
        "tts",
        "hyperframes_material",
    }
)
SOURCE_PROVIDERS = frozenset(
    {"asset_reuse", "stock_media_search", "image_generation", "video_generation"}
)
COMPLETION_MODES = frozenset(
    {"source_only", "source_then_polish", "hf_native", "packaging_only"}
)
AIGC_PROVIDERS = frozenset({"image_generation", "video_generation"})
DEFAULT_COST_ORDER = (
    "asset_reuse",
    "stock_media_search",
    "hyperframes_material",
    "image_generation",
    "video_generation",
)


def _slot_id(slot: dict[str, Any]) -> str:
    return str(slot.get("id", ""))


def _normalize_mode(value: str | None, *, default: str = "source_only") -> str:
    mode = str(value or default).strip()
    return mode if mode in COMPLETION_MODES else default


def _packaging_forced(slot: dict[str, Any]) -> bool:
    role = normalize_slot_role(str(slot.get("role", "")))
    required = list(slot.get("requiredAssetType") or [])
    return role in GAP_HYPERFRAMES_PRIMARY_ROLES or "packaging" in required


def _default_mode_for_slot(slot: dict[str, Any]) -> str:
    role = normalize_slot_role(str(slot.get("role", "")))
    if role in GAP_HYPERFRAMES_PRIMARY_ROLES:
        return "hf_native"
    return "source_only"


def _llm_chain(llm_item: dict[str, Any]) -> list[str]:
    fixes = llm_item.get("suggestedFixes")
    if not isinstance(fixes, list):
        return []
    chain: list[str] = []
    for item in fixes:
        provider = str(item or "").strip()
        if provider in MATERIAL_PROVIDERS and provider not in chain:
            chain.append(provider)
    return chain


def _llm_allows_video_generation(llm_item: dict[str, Any]) -> bool:
    """Allow retained video_generation when LLM documents must-use AIGC intent."""
    text = " ".join(
        str(llm_item.get(key, "") or "")
        for key in ("reason", "finishIntent", "reconcileNotes")
    ).lower()
    markers = (
        "must-use",
        "must use",
        "aigc",
        "video_generation",
        "生视频",
        "图生视频",
        "文生视频",
        "i2v",
        "t2v",
        "product_closeup",
        "本品",
        "generated_visual",
    )
    return any(marker in text for marker in markers)


def aigc_required(
    slot: dict[str, Any],
    *,
    weak_match: dict[str, Any] | None,
    inventory: dict[str, Any] | None,
) -> bool:
    role = normalize_slot_role(str(slot.get("role", "")))
    required = list(slot.get("requiredAssetType") or [])
    brief = (inventory or {}).get("userBrief") if isinstance((inventory or {}).get("userBrief"), dict) else {}

    if role == PRODUCT_CLOSEUP_ROLE and is_product_bound_brief(brief):
        return True
    if "generated_visual" in required and "packaging" not in required:
        return True
    return False


def _sort_sources_by_cost(sources: list[str], *, variant_overrides: dict[str, Any] | None) -> list[str]:
    overrides = variant_overrides or {}
    prefer = [str(p) for p in (overrides.get("preferProviders") or []) if str(p).strip()]
    order = prefer or list(DEFAULT_COST_ORDER)
    rank = {name: index for index, name in enumerate(order)}

    seen: set[str] = set()
    deduped: list[str] = []
    for name in sources:
        if name not in MATERIAL_PROVIDERS or name in seen:
            continue
        seen.add(name)
        deduped.append(name)
    return sorted(deduped, key=lambda name: (rank.get(name, len(order)), deduped.index(name)))


def reorder_by_cost_policy(
    chain: list[str],
    *,
    variant_overrides: dict[str, Any] | None,
) -> list[str]:
    if not chain:
        return chain

    finish_tail: list[str] = []
    sources = list(chain)
    if len(sources) > 1 and sources[-1] == "hyperframes_material":
        finish_tail = ["hyperframes_material"]
        sources = sources[:-1]

    ordered_sources = _sort_sources_by_cost(sources, variant_overrides=variant_overrides)
    return ordered_sources + finish_tail


def _enforce_hard_rules(
    chain: list[str],
    *,
    slot: dict[str, Any],
    weak_match: dict[str, Any] | None,
    inventory: dict[str, Any] | None,
    quota: VideoGenQuota,
    slot_id: str,
    llm_item: dict[str, Any],
) -> tuple[list[str], list[str]]:
    notes: list[str] = []
    role = normalize_slot_role(str(slot.get("role", "")))
    required = list(slot.get("requiredAssetType") or [])
    brief = (inventory or {}).get("userBrief") if isinstance((inventory or {}).get("userBrief"), dict) else {}
    result = list(chain)

    if role == PRODUCT_CLOSEUP_ROLE and "stock_media_search" in result:
        result = [p for p in result if p != "stock_media_search"]
        notes.append("removed_stock_for_product_closeup")

    if weak_match is not None:
        asset_type = resolve_match_asset_type(weak_match, inventory or {})
        if asset_type == "video" and "asset_reuse" not in result:
            result.insert(0, "asset_reuse")
            notes.append("injected_asset_reuse_for_video_weak_match")
        if asset_type == "image" and "asset_reuse" in result:
            result = [p for p in result if p != "asset_reuse"]
            notes.append("removed_asset_reuse_for_image_weak_match")

    if "video_generation" in result and not quota.can_generate_for_slot(slot_id):
        result = [("image_generation" if p == "video_generation" else p) for p in result]
        notes.append("downgraded_video_generation_no_quota")

    if not aigc_required(slot, weak_match=weak_match, inventory=inventory):
        if "video_generation" in result and not _llm_allows_video_generation(llm_item):
            result = [p for p in result if p != "video_generation"]
            notes.append("removed_video_generation_without_llm_must_use")
        filtered = [p for p in result if p not in AIGC_PROVIDERS]
        if filtered:
            result = filtered
        elif any(p in AIGC_PROVIDERS for p in result):
            result = ["hyperframes_material"]
        notes.append("removed_aigc_not_required")

    if _packaging_forced(slot):
        if "hyperframes_material" not in result:
            result.append("hyperframes_material")
            notes.append("injected_hyperframes_for_packaging_role")

    deduped: list[str] = []
    seen: set[str] = set()
    for name in result:
        if name not in MATERIAL_PROVIDERS or name in seen:
            continue
        seen.add(name)
        deduped.append(name)
    return deduped, notes


def _apply_completion_mode(
    chain: list[str],
    mode: str,
    *,
    slot: dict[str, Any],
) -> tuple[list[str], str, list[str]]:
    notes: list[str] = []
    role = normalize_slot_role(str(slot.get("role", "")))
    result = list(chain)
    packaging_forced = _packaging_forced(slot)

    if mode in {"hf_native", "packaging_only"}:
        if result != ["hyperframes_material"]:
            result = ["hyperframes_material"]
            notes.append(f"mode_{mode}_forces_hf_native")
        return result, mode, notes

    if mode == "source_only":
        if packaging_forced:
            if role in GAP_HYPERFRAMES_PRIMARY_ROLES and not any(p in SOURCE_PROVIDERS for p in result):
                result = ["hyperframes_material"]
                notes.append("packaging_role_hf_native")
                return result, "hf_native", notes
            if len(result) > 1 and result[-1] == "hyperframes_material":
                notes.append("packaging_keeps_hf_finish")
                return result, mode, notes
        if len(result) > 1 and result[-1] == "hyperframes_material":
            result = [p for p in result if p != "hyperframes_material"]
            notes.append("source_only_strips_finish")
        return result, mode, notes

    if mode == "source_then_polish" and "hyperframes_material" not in result:
        result.append("hyperframes_material")
        notes.append("appended_hf_finish")
    return result, mode, notes


def reconcile_provider_chain(
    *,
    llm_item: dict[str, Any],
    slot: dict[str, Any],
    weak_match: dict[str, Any] | None,
    quota: VideoGenQuota,
    inventory: dict[str, Any] | None,
    variant_overrides: dict[str, Any] | None,
) -> tuple[list[str], str, str]:
    slot_id = _slot_id(slot)
    mode = _normalize_mode(llm_item.get("completionMode"), default=_default_mode_for_slot(slot))
    llm_chain = _llm_chain(llm_item)

    if llm_chain:
        chain = list(llm_chain)
        notes_prefix = "llm_chain_accepted"
    else:
        chain = select_provider_chain(
            slot,
            weak_match=weak_match,
            quota=quota,
            inventory=inventory,
            variant_overrides=variant_overrides,
            impact=str(llm_item.get("impact", "medium")),
        )
        notes_prefix = "fallback_select_provider_chain"

    chain = reorder_by_cost_policy(chain, variant_overrides=variant_overrides)
    chain, rule_notes = _enforce_hard_rules(
        chain,
        slot=slot,
        weak_match=weak_match,
        inventory=inventory,
        quota=quota,
        slot_id=slot_id,
        llm_item=llm_item,
    )
    chain, mode, mode_notes = _apply_completion_mode(chain, mode, slot=slot)

    if not chain:
        chain = select_provider_chain(
            slot,
            weak_match=weak_match,
            quota=quota,
            inventory=inventory,
            variant_overrides=variant_overrides,
        )

    all_notes = [notes_prefix, *rule_notes, *mode_notes]
    return chain, mode, "; ".join(note for note in all_notes if note)
