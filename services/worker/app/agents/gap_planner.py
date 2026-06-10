from __future__ import annotations

from typing import Any

from app.agents.runner import AgentRunner
from app.config.variants import load_variant_gap_planner_overrides
from app.pipelines.gap_reconcile import reconcile_provider_chain, resolve_finish_intent_from_variant
from app.pipelines.gap_selection import provider_rationale
from app.runtime.video_gen_quota import VideoGenQuota
from app.agents.slot_mapper import classify_slot_matches
from app.runtime.task_context import TaskContext


TASK_KEY = "gap_planner"
SCHEMA_NAME = "gap-report"


def _slots_by_id(structure: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        slot["id"]: slot
        for slot in structure.get("slots", [])
        if isinstance(slot, dict) and slot.get("id")
    }


def _match_for_slot(slot_id: str, slot_matches: list[dict[str, Any]]) -> dict[str, Any] | None:
    for match in slot_matches:
        if match.get("slotId") == slot_id:
            return match
    return None


def _default_impact(slot: dict[str, Any]) -> str:
    return "high" if slot.get("importance") == "must_have" else "medium"


def _default_gap_reason(slot_id: str, *, bucket: str) -> str:
    if bucket == "missingSlots":
        return f"槽位 {slot_id} 缺少可用素材匹配"
    return f"槽位 {slot_id} 仅有弱匹配素材"


def reconcile_gap_buckets(
    gap_report: dict[str, Any],
    *,
    structure: dict[str, Any],
    slot_matches: list[dict[str, Any]],
) -> dict[str, Any]:
    """Rebuild weak/missing buckets from Python classify_slot_matches (authoritative)."""
    slots = _slots_by_id(structure)
    _, weak_ids, missing_ids = classify_slot_matches(structure, slot_matches)

    hints_by_slot: dict[str, dict[str, Any]] = {}
    for bucket in ("weakSlots", "missingSlots"):
        for item in gap_report.get(bucket, []):
            if isinstance(item, dict) and item.get("slotId"):
                hints_by_slot[str(item["slotId"])] = item

    weak_slots: list[dict[str, Any]] = []
    for slot_id in weak_ids:
        slot = slots.get(slot_id, {})
        hint = hints_by_slot.get(slot_id, {})
        weak_slots.append(
            {
                "slotId": slot_id,
                "reason": str(hint.get("reason", "")).strip() or _default_gap_reason(slot_id, bucket="weakSlots"),
                "impact": hint.get("impact") or _default_impact(slot),
                "suggestedFixes": list(hint.get("suggestedFixes") or ["hyperframes_material"]),
                **(
                    {"completionMode": hint["completionMode"]}
                    if hint.get("completionMode")
                    else {}
                ),
                **({"finishIntent": hint["finishIntent"]} if hint.get("finishIntent") else {}),
            }
        )

    missing_slots: list[dict[str, Any]] = []
    for slot_id in missing_ids:
        slot = slots.get(slot_id, {})
        hint = hints_by_slot.get(slot_id, {})
        missing_slots.append(
            {
                "slotId": slot_id,
                "reason": str(hint.get("reason", "")).strip() or _default_gap_reason(slot_id, bucket="missingSlots"),
                "impact": hint.get("impact") or _default_impact(slot),
                "suggestedFixes": list(hint.get("suggestedFixes") or ["hyperframes_material"]),
                **(
                    {"completionMode": hint["completionMode"]}
                    if hint.get("completionMode")
                    else {}
                ),
                **({"finishIntent": hint["finishIntent"]} if hint.get("finishIntent") else {}),
            }
        )

    gap_report["weakSlots"] = weak_slots
    gap_report["missingSlots"] = missing_slots
    gap_report["summary"] = f"{len(missing_slots)} missing, {len(weak_slots)} weak slots"
    return gap_report


def _compose_gap_reason(
    *,
    diagnosis: str,
    primary_provider: str,
    slot: dict[str, Any],
    weak_match: dict[str, Any] | None,
    providers: list[str],
) -> str:
    strategy = provider_rationale(primary_provider, slot, weak_match=weak_match)
    if len(providers) > 1 and providers[-1] == "hyperframes_material":
        if primary_provider in {"stock_media_search", "asset_reuse", "video_generation"}:
            strategy = f"{strategy}；后续用 hyperframes_material 对底片做 overlay 润色"
        else:
            strategy = f"{strategy}；后续用 hyperframes_material 做 ken-burns 动效"
    diagnosis = diagnosis.strip()
    if diagnosis:
        return f"{diagnosis}；补全策略：{strategy}"
    return strategy


def apply_provider_reconciliation(
    gap_report: dict[str, Any],
    *,
    structure: dict[str, Any],
    slot_matches: list[dict[str, Any]],
    inventory: dict[str, Any] | None = None,
    quota: VideoGenQuota | None = None,
    variant_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    slots = _slots_by_id(structure)
    quota = quota or VideoGenQuota.from_env()
    overrides = variant_overrides or {}

    for bucket in ("missingSlots", "weakSlots"):
        updated: list[dict[str, Any]] = []
        for item in gap_report.get(bucket, []):
            if not isinstance(item, dict):
                continue
            slot_id = item.get("slotId")
            slot = slots.get(slot_id)
            if slot is None:
                updated.append(item)
                continue
            weak_match = _match_for_slot(slot_id, slot_matches)
            providers, mode, notes = reconcile_provider_chain(
                llm_item=item,
                slot=slot,
                weak_match=weak_match,
                quota=quota,
                inventory=inventory,
                variant_overrides=overrides,
            )
            primary = providers[0]
            reason = _compose_gap_reason(
                diagnosis=str(item.get("reason", "")),
                primary_provider=primary,
                slot=slot,
                weak_match=weak_match,
                providers=providers,
            )
            merged_item = {
                **item,
                "reason": reason,
                "suggestedFixes": providers,
                "completionMode": mode,
                "reconcileNotes": notes,
            }
            if not str(merged_item.get("finishIntent", "")).strip():
                default_intent = resolve_finish_intent_from_variant(slot, overrides)
                if default_intent and mode in {"source_then_polish", "hf_native", "packaging_only"}:
                    merged_item["finishIntent"] = default_intent
            updated.append(merged_item)
        gap_report[bucket] = updated
    return gap_report


def apply_provider_selection(
    gap_report: dict[str, Any],
    *,
    structure: dict[str, Any],
    slot_matches: list[dict[str, Any]],
    inventory: dict[str, Any] | None = None,
    quota: VideoGenQuota | None = None,
    variant_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Backward-compatible alias for ``apply_provider_reconciliation``."""
    return apply_provider_reconciliation(
        gap_report,
        structure=structure,
        slot_matches=slot_matches,
        inventory=inventory,
        quota=quota,
        variant_overrides=variant_overrides,
    )


def run_gap_planner(
    runner: AgentRunner,
    *,
    structure: dict[str, Any],
    inventory: dict[str, Any],
    slot_matches: list[dict[str, Any]],
    context: TaskContext,
    progress: int = 45,
    generation_id: str | None = None,
    variant: str = "default",
    quota: VideoGenQuota | None = None,
    knowledge_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    variant_overrides = load_variant_gap_planner_overrides(variant)
    _, weak_ids, missing_ids = classify_slot_matches(structure, slot_matches)
    quota_state = quota or VideoGenQuota.from_env()

    inputs: dict[str, Any] = {
        "structure": structure,
        "inventory": inventory,
        "slotMatches": slot_matches,
        "weakSlotIds": weak_ids,
        "missingSlotIds": missing_ids,
        "variantOverrides": variant_overrides,
        "videoGenQuotaRemaining": quota_state.remaining_slots,
        "videoGenMaxSlots": quota_state.max_slots,
        "videoGenMaxPerSlot": quota_state.max_per_slot,
    }
    if knowledge_context:
        inputs["knowledgeContext"] = knowledge_context

    gap_report = runner.run(
        "gap_planner",
        task=TASK_KEY,
        schema_name=SCHEMA_NAME,
        inputs=inputs,
        context=context,
        progress=progress,
        generation_id=generation_id,
    )
    gap_report["slotMatches"] = slot_matches
    gap_report = reconcile_gap_buckets(
        gap_report,
        structure=structure,
        slot_matches=slot_matches,
    )
    gap_report = apply_provider_reconciliation(
        gap_report,
        structure=structure,
        slot_matches=slot_matches,
        inventory=inventory,
        quota=quota_state,
        variant_overrides=variant_overrides,
    )
    return gap_report
