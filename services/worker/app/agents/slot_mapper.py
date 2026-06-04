from __future__ import annotations

import re
from typing import Any

from app.agents.runner import AgentRunner
from app.runtime.task_context import TaskContext
from app.validation.schema_loader import validate_contract

TASK_KEY = "slot_mapper"

MATCHED_THRESHOLD = 0.62
WEAK_THRESHOLD = 0.38
SCORE_CLAMP_DELTA = 0.25

IMPORTANCE_WEIGHTS = {
    "must_have": 1.0,
    "recommended": 0.8,
    "optional": 0.5,
}

_TYPE_WEIGHT = 0.35
_DURATION_WEIGHT = 0.15
_SEMANTIC_WEIGHT = 0.4


def _importance_weight(slot: dict[str, Any]) -> float:
    return IMPORTANCE_WEIGHTS.get(str(slot.get("importance", "recommended")), 0.8)


def _normalize_tokens(text: str) -> set[str]:
    if not text:
        return set()
    parts = re.findall(r"[\u4e00-\u9fff]+|[a-zA-Z0-9]+", text.lower())
    return {part for part in parts if part}


def _resolve_asset_type(
    asset_id: str | None,
    moment_id: str | None,
    inventory: dict[str, Any],
) -> str | None:
    assets_by_id = {
        asset["id"]: asset.get("type")
        for asset in inventory.get("assets", [])
        if isinstance(asset, dict) and asset.get("id")
    }
    if asset_id and asset_id in assets_by_id:
        return str(assets_by_id[asset_id])
    if moment_id:
        for moment in inventory.get("candidateMoments", []):
            if isinstance(moment, dict) and moment.get("id") == moment_id:
                linked = moment.get("assetId")
                if linked and linked in assets_by_id:
                    return str(assets_by_id[linked])
    return None


def _type_score(slot: dict[str, Any], asset_type: str | None) -> float:
    if not asset_type:
        return 0.0
    required = list(slot.get("requiredAssetType") or [])
    if asset_type in required:
        return 1.0
    if asset_type == "text" and any(item in required for item in ("text", "packaging")):
        return 1.0
    if asset_type == "text" and any(item in required for item in ("video", "image")):
        return 0.5
    return 0.0


def _duration_score(
    slot: dict[str, Any],
    asset_type: str | None,
    asset_id: str | None,
    moment_id: str | None,
    inventory: dict[str, Any],
) -> float:
    if asset_type == "text":
        return 0.6
    if asset_type == "image":
        return 0.7
    if asset_type != "video":
        return 0.0

    slot_duration = max(0.1, float(slot.get("endSec", 0)) - float(slot.get("startSec", 0)))
    candidate_duration: float | None = None
    if moment_id:
        for moment in inventory.get("candidateMoments", []):
            if isinstance(moment, dict) and moment.get("id") == moment_id:
                candidate_duration = max(
                    0.1,
                    float(moment.get("endSec", 0)) - float(moment.get("startSec", 0)),
                )
                break
    if candidate_duration is None and asset_id:
        for asset in inventory.get("assets", []):
            if isinstance(asset, dict) and asset.get("id") == asset_id:
                if asset.get("durationSec") is not None:
                    candidate_duration = max(0.1, float(asset["durationSec"]))
                break
    if candidate_duration is None:
        return 0.0
    return min(1.0, candidate_duration / slot_duration)


def _semantic_score(
    slot: dict[str, Any],
    asset_id: str | None,
    moment_id: str | None,
    inventory: dict[str, Any],
) -> float:
    slot_tokens = _normalize_tokens(
        " ".join(
            [
                str(slot.get("visualIntent", "")),
                str(slot.get("scriptIntent", "")),
                str(slot.get("role", "")),
            ]
        )
    )
    if not slot_tokens:
        return 0.0

    tag_tokens: set[str] = set()
    if asset_id:
        for asset in inventory.get("assets", []):
            if isinstance(asset, dict) and asset.get("id") == asset_id:
                tag_tokens.update(_normalize_tokens(str(asset.get("description", ""))))
                for tag in asset.get("tags", []):
                    tag_tokens.update(_normalize_tokens(str(tag)))
                break
    if moment_id:
        for moment in inventory.get("candidateMoments", []):
            if isinstance(moment, dict) and moment.get("id") == moment_id:
                tag_tokens.update(_normalize_tokens(str(moment.get("description", ""))))
                for tag in moment.get("tags", []):
                    tag_tokens.update(_normalize_tokens(str(tag)))
                break

    for fact in inventory.get("extractedFacts", []):
        if isinstance(fact, dict):
            tag_tokens.update(_normalize_tokens(str(fact.get("text", ""))))

    if not tag_tokens:
        return 0.0
    overlap = len(slot_tokens & tag_tokens)
    union = len(slot_tokens | tag_tokens)
    return overlap / union if union else 0.0


def compute_match_score(
    slot: dict[str, Any],
    match: dict[str, Any],
    inventory: dict[str, Any],
) -> float:
    asset_id = match.get("assetId")
    moment_id = match.get("momentId")
    asset_type = _resolve_asset_type(
        str(asset_id) if asset_id else None,
        str(moment_id) if moment_id else None,
        inventory,
    )
    type_score = _type_score(slot, asset_type)
    duration_score = _duration_score(slot, asset_type, asset_id, moment_id, inventory)
    semantic_score = _semantic_score(slot, asset_id, moment_id, inventory)
    weight = _importance_weight(slot)
    return (
        type_score * _TYPE_WEIGHT
        + semantic_score * _SEMANTIC_WEIGHT
        + duration_score * _DURATION_WEIGHT
    ) * weight


def _structural_bounds(slot: dict[str, Any], match: dict[str, Any], inventory: dict[str, Any]) -> tuple[float, float]:
    asset_id = match.get("assetId")
    moment_id = match.get("momentId")
    asset_type = _resolve_asset_type(
        str(asset_id) if asset_id else None,
        str(moment_id) if moment_id else None,
        inventory,
    )
    type_score = _type_score(slot, asset_type)
    duration_score = _duration_score(slot, asset_type, asset_id, moment_id, inventory)
    weight = _importance_weight(slot)
    floor = (type_score * _TYPE_WEIGHT + duration_score * _DURATION_WEIGHT) * weight
    ceiling = floor + _SEMANTIC_WEIGHT * weight
    return floor, ceiling


def _ensure_natural_language_reason(reason: str) -> str:
    stripped = reason.strip()
    if not stripped:
        return "素材与槽位意图部分匹配"
    if re.search(r"type=\d|semantic=\d|duration=\d", stripped):
        return "素材类型或时长与槽位要求部分吻合，语义覆盖有限"
    return stripped


def post_validate_slot_matches(
    slot_matches: list[dict[str, Any]],
    *,
    structure: dict[str, Any],
    inventory: dict[str, Any],
) -> list[dict[str, Any]]:
    slots_by_id = {
        slot["id"]: slot
        for slot in structure.get("slots", [])
        if isinstance(slot, dict) and slot.get("id")
    }
    validated: list[dict[str, Any]] = []

    for match in slot_matches:
        slot_id = match.get("slotId")
        slot = slots_by_id.get(slot_id)
        if slot is None:
            continue

        agent_score = float(match.get("matchScore", 0))
        recomputed = compute_match_score(slot, match, inventory)
        floor, ceiling = _structural_bounds(slot, match, inventory)
        clamped = max(floor, min(ceiling, agent_score))
        if abs(recomputed - agent_score) > SCORE_CLAMP_DELTA:
            clamped = max(0.0, min(1.0, recomputed))
        elif abs(clamped - agent_score) > SCORE_CLAMP_DELTA:
            clamped = max(0.0, min(1.0, clamped))

        reason = _ensure_natural_language_reason(str(match.get("matchReason", "")))
        if abs(clamped - agent_score) > 0.01:
            reason = f"{reason}（类型/时长校验后分数调整为 {clamped:.2f}）"

        validated.append(
            {
                **match,
                "matchScore": round(clamped, 3),
                "matchReason": reason,
            }
        )
    return validated


def classify_slot_matches(
    structure: dict[str, Any],
    slot_matches: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    """Return matched list, weak slot ids, missing slot ids."""
    matches_by_slot = {match["slotId"]: match for match in slot_matches if match.get("slotId")}
    matched: list[dict[str, Any]] = []
    weak_ids: list[str] = []
    missing_ids: list[str] = []

    for slot in structure.get("slots", []):
        if not isinstance(slot, dict) or not slot.get("id"):
            continue
        slot_id = slot["id"]
        match = matches_by_slot.get(slot_id)
        if match is None:
            missing_ids.append(slot_id)
            continue
        score = float(match.get("matchScore", 0))
        if score >= MATCHED_THRESHOLD:
            matched.append(match)
        elif score >= WEAK_THRESHOLD:
            weak_ids.append(slot_id)
            matched.append(match)
        else:
            missing_ids.append(slot_id)
    return matched, weak_ids, missing_ids


def _assert_slot_matches(payload: dict[str, Any]) -> dict[str, Any]:
    slot_matches = payload.get("slotMatches")
    if not isinstance(slot_matches, list):
        raise ValueError("slot_mapper output must include slotMatches array")
    for match in slot_matches:
        if not isinstance(match, dict):
            raise ValueError("slotMatches items must be objects")
        if not str(match.get("matchReason", "")).strip():
            raise ValueError("slotMatches items must include natural-language matchReason")
        probe = {
            "id": "gap-probe",
            "projectId": "probe",
            "structureId": "probe",
            "inventoryId": "probe",
            "slotMatches": [match],
            "missingSlots": [],
            "weakSlots": [],
            "summary": "probe",
        }
        validation = validate_contract("gap-report", probe)
        if not validation.valid:
            raise ValueError(f"Invalid slot match: {validation.errors}")
    return payload


def run_slot_mapper(
    runner: AgentRunner,
    *,
    structure: dict[str, Any],
    inventory: dict[str, Any],
    context: TaskContext,
    progress: int = 35,
    generation_id: str | None = None,
    variant_overrides: dict[str, Any] | None = None,
    knowledge_context: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    inputs: dict[str, Any] = {
        "videoStructure": structure,
        "assetInventory": inventory,
        "variantOverrides": variant_overrides or {},
    }
    if knowledge_context:
        inputs["knowledgeContext"] = knowledge_context
    output = runner.run(
        "slot_mapper",
        task=TASK_KEY,
        schema_name=None,
        inputs=inputs,
        context=context,
        progress=progress,
        generation_id=generation_id,
        post_validate=_assert_slot_matches,
    )
    return post_validate_slot_matches(
        output["slotMatches"],
        structure=structure,
        inventory=inventory,
    )
