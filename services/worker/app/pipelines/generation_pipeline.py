from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.validation.schema_loader import validate_contract


IMPORTANCE_WEIGHT = {"must_have": 1.0, "recommended": 0.8, "optional": 0.5}
TRACK_ORDER = ["video", "image", "text", "effect", "transition", "voiceover", "bgm"]
KEYWORD_TOKENS = {
    "真实",
    "使用",
    "效率",
    "提升",
    "产品",
    "场景",
    "对比",
    "购买",
    "点击",
    "benefit",
    "proof",
    "solution",
    "hook",
    "cta",
}


@dataclass(frozen=True)
class SlotMappingResult:
    slot_matches: list[dict[str, Any]]


def build_asset_inventory(
    *,
    project_id: str,
    user_brief: dict[str, Any],
    assets: list[dict[str, Any]],
) -> dict[str, Any]:
    brief = {
        "topic": user_brief.get("topic"),
        "productName": user_brief.get("productName"),
        "sellingPoints": list(user_brief.get("sellingPoints", [])),
        "targetAudience": user_brief.get("targetAudience"),
        "tone": user_brief.get("tone"),
        "mustMention": list(user_brief.get("mustMention", [])),
        "avoidMention": list(user_brief.get("avoidMention", [])),
    }

    normalized_assets = []
    for asset in assets:
        normalized = {
            "id": asset["id"],
            "type": asset["type"],
            "uri": asset["uri"],
            "description": asset.get("description", ""),
            "tags": list(asset.get("tags", [])),
        }
        if asset.get("durationSec") is not None:
            normalized["durationSec"] = float(asset["durationSec"])
        normalized_assets.append(normalized)

    extracted_facts = []
    fact_index = 1
    for point in brief["sellingPoints"]:
        extracted_facts.append(
            {
                "id": f"fact-{fact_index}",
                "kind": "selling_point",
                "text": point,
                "source": "brief.sellingPoints",
            }
        )
        fact_index += 1
    if brief.get("targetAudience"):
        extracted_facts.append(
            {
                "id": f"fact-{fact_index}",
                "kind": "audience",
                "text": brief["targetAudience"],
                "source": "brief.targetAudience",
            }
        )
        fact_index += 1
    for text in brief["mustMention"]:
        extracted_facts.append(
            {
                "id": f"fact-{fact_index}",
                "kind": "constraint",
                "text": text,
                "source": "brief.mustMention",
            }
        )
        fact_index += 1
    for text in brief["avoidMention"]:
        extracted_facts.append(
            {
                "id": f"fact-{fact_index}",
                "kind": "constraint",
                "text": text,
                "source": "brief.avoidMention",
            }
        )
        fact_index += 1

    candidate_moments = []
    for asset in normalized_assets:
        duration = float(asset.get("durationSec", 3.0))
        if asset["type"] == "video":
            candidate_moments.append(
                {
                    "id": f"moment-{asset['id']}-full",
                    "assetId": asset["id"],
                    "startSec": 0.0,
                    "endSec": max(0.1, duration),
                    "description": asset.get("description", "") or f"moment from {asset['id']}",
                    "tags": _build_asset_tokens(asset),
                }
            )

    inventory = {
        "id": f"inventory-{project_id}",
        "projectId": project_id,
        "userBrief": {key: value for key, value in brief.items() if value is not None},
        "assets": normalized_assets,
        "extractedFacts": extracted_facts,
        "candidateMoments": candidate_moments,
    }
    validation = validate_contract("asset-inventory", inventory)
    if not validation.valid:
        raise ValueError(f"Invalid AssetInventory payload: {validation.errors}")
    return inventory


def map_slots(*, structure: dict[str, Any], inventory: dict[str, Any]) -> SlotMappingResult:
    assets = inventory.get("assets", [])
    moments_by_asset = {}
    for moment in inventory.get("candidateMoments", []):
        moments_by_asset.setdefault(moment["assetId"], []).append(moment)

    used_assets: set[str] = set()
    slots = sorted(
        structure.get("slots", []),
        key=lambda slot: IMPORTANCE_WEIGHT.get(slot.get("importance", "optional"), 0.5),
        reverse=True,
    )

    slot_matches: list[dict[str, Any]] = []
    for slot in slots:
        candidates: list[dict[str, Any]] = []
        slot_tokens = _tokenize(
            " ".join(
                [
                    str(slot.get("visualIntent", "")),
                    str(slot.get("scriptIntent", "")),
                    str(slot.get("packagingHint", "")),
                ]
            )
        )
        required_types = set(slot.get("requiredAssetType", []))
        slot_duration = max(0.01, float(slot["endSec"]) - float(slot["startSec"]))
        slot_is_visual = bool({"video", "image"} & required_types)

        for asset in assets:
            asset_tokens = set(_build_asset_tokens(asset))
            semantic_score = _jaccard(slot_tokens, asset_tokens)
            type_score = _type_score(required_types=required_types, asset=asset, slot_is_visual=slot_is_visual)
            duration_score, moment_id = _duration_score(
                slot_duration=slot_duration,
                asset=asset,
                moments=moments_by_asset.get(asset["id"], []),
            )
            importance = IMPORTANCE_WEIGHT.get(slot.get("importance", "optional"), 0.5)
            match_score = (
                (type_score * 0.35 + semantic_score * 0.4 + duration_score * 0.15) * importance
            )
            candidates.append(
                {
                    "slotId": slot["id"],
                    "assetId": asset["id"],
                    "momentId": moment_id,
                    "matchScore": round(max(0.0, min(1.0, match_score)), 4),
                    "matchReason": _reason_text(type_score, semantic_score, duration_score),
                    "_isVideo": asset["type"] == "video",
                    "_durationDiff": abs(
                        slot_duration - float(asset.get("durationSec", slot_duration))
                    ),
                    "_alreadyUsed": asset["id"] in used_assets,
                }
            )

        if not candidates:
            slot_matches.append(
                {
                    "slotId": slot["id"],
                    "matchScore": 0.0,
                    "matchReason": "No candidate assets",
                }
            )
            continue

        candidates.sort(
            key=lambda item: (
                item["matchScore"],
                1 if item["_isVideo"] else 0,
                -item["_durationDiff"],
                0 if item["_alreadyUsed"] else 1,
            ),
            reverse=True,
        )
        best = {
            key: value
            for key, value in candidates[0].items()
            if not key.startswith("_") and value is not None
        }
        if best.get("assetId"):
            used_assets.add(str(best["assetId"]))
        slot_matches.append(best)

    return SlotMappingResult(slot_matches=slot_matches)


def build_gap_report(
    *,
    structure: dict[str, Any],
    inventory: dict[str, Any],
    slot_matches: list[dict[str, Any]],
) -> dict[str, Any]:
    slots_by_id = {slot["id"]: slot for slot in structure.get("slots", [])}
    missing_slots = []
    weak_slots = []

    for match in slot_matches:
        slot = slots_by_id.get(match["slotId"])
        if slot is None:
            continue
        score = float(match.get("matchScore", 0.0))
        if score >= 0.62:
            continue

        impact = _impact_from_importance(slot.get("importance", "optional"))
        has_visual_partial = score >= 0.38 and bool(match.get("assetId"))
        suggested_fixes = _suggest_fixes(
            slot=slot,
            visual_density=structure.get("packaging", {}).get("visualDensity", "medium"),
            has_visual_partial=has_visual_partial,
            inventory=inventory,
        )
        record = {
            "slotId": slot["id"],
            "reason": "Partial match but not strong enough"
            if has_visual_partial
            else "No reliable asset match for slot intent",
            "impact": impact,
            "suggestedFixes": suggested_fixes,
        }
        if score >= 0.38:
            weak_slots.append(record)
        else:
            missing_slots.append(record)

    report = {
        "id": f"gap-report-{structure['projectId']}",
        "projectId": structure["projectId"],
        "structureId": structure["id"],
        "inventoryId": inventory["id"],
        "slotMatches": slot_matches,
        "missingSlots": missing_slots,
        "weakSlots": weak_slots,
        "summary": f"{len(missing_slots)} missing, {len(weak_slots)} weak slots",
    }
    validation = validate_contract("gap-report", report)
    if not validation.valid:
        raise ValueError(f"Invalid GapReport payload: {validation.errors}")
    return report


def build_generation_plan(
    *,
    structure: dict[str, Any],
    inventory: dict[str, Any],
    gap_report: dict[str, Any],
    slot_matches: list[dict[str, Any]],
    variant: str = "default",
) -> dict[str, Any]:
    slots_by_id = {slot["id"]: slot for slot in structure.get("slots", [])}
    matches_by_slot = {match["slotId"]: match for match in slot_matches}

    weak_ids = {item["slotId"] for item in gap_report.get("weakSlots", [])}
    missing_ids = {item["slotId"] for item in gap_report.get("missingSlots", [])}
    gap_by_slot = {
        item["slotId"]: item
        for item in [*gap_report.get("weakSlots", []), *gap_report.get("missingSlots", [])]
    }

    storyboard = []
    completion_actions = []
    for index, slot in enumerate(structure.get("slots", []), start=1):
        slot_id = slot["id"]
        match = matches_by_slot.get(slot_id, {})
        source = "user_asset"
        if slot_id in missing_ids:
            source = _source_from_fix(gap_by_slot[slot_id]["suggestedFixes"][0])
        elif slot_id in weak_ids:
            source = _source_from_fix(gap_by_slot[slot_id]["suggestedFixes"][0])
        elif match.get("assetId") and slot_id not in missing_ids and slot_id not in weak_ids:
            source = "user_asset"

        storyboard.append(
            {
                "id": f"scene-{index}",
                "slotId": slot_id,
                "startSec": slot["startSec"],
                "endSec": slot["endSec"],
                "visual": slot["visualIntent"],
                "script": slot["scriptIntent"],
                "source": source,
            }
        )

        if slot_id in gap_by_slot:
            fix = gap_by_slot[slot_id]["suggestedFixes"][0]
            completion_actions.append(
                {
                    "id": f"action-{slot_id}",
                    "slotId": slot_id,
                    "strategy": fix,
                    "reason": gap_by_slot[slot_id]["reason"],
                    "outputRef": f"completion://{slot_id}/{fix}",
                }
            )

    timeline = _build_timeline(storyboard=storyboard, slot_matches=matches_by_slot, slots=slots_by_id)
    duration = max((scene["endSec"] for scene in storyboard), default=0.0)
    timeline["durationSec"] = duration

    plan = {
        "id": f"generation-plan-{structure['projectId']}",
        "projectId": structure["projectId"],
        "structureId": structure["id"],
        "inventoryId": inventory["id"],
        "gapReportId": gap_report["id"],
        "variant": variant,
        "storyboard": storyboard,
        "timeline": timeline,
        "packagingPlan": {
            "styleSummary": f"Visual density: {structure.get('packaging', {}).get('visualDensity', 'medium')}",
            "subtitle": {"preset": "clean"},
            "titleCards": [{"preset": "hook"}],
            "transitions": [{"preset": "quick-cut"}],
        },
        "completionActions": completion_actions,
    }
    validation = validate_contract("generation-plan", plan)
    if not validation.valid:
        raise ValueError(f"Invalid GenerationPlan payload: {validation.errors}")
    return plan


def _build_timeline(
    *,
    storyboard: list[dict[str, Any]],
    slot_matches: dict[str, dict[str, Any]],
    slots: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    tracks = {track_type: {"id": f"track-{track_type}", "type": track_type, "clips": []} for track_type in TRACK_ORDER}

    for scene in storyboard:
        slot_id = scene["slotId"]
        match = slot_matches.get(slot_id, {})
        slot = slots[slot_id]
        clip = {
            "id": f"clip-{slot_id}",
            "startSec": scene["startSec"],
            "endSec": scene["endSec"],
        }

        if scene["source"] in {"user_asset", "asset_reuse"} and match.get("assetId"):
            asset_id = str(match["assetId"])
            if match.get("momentId"):
                clip["sourceRef"] = str(match["momentId"])
                tracks["video"]["clips"].append(clip)
            elif "image" in slot.get("requiredAssetType", []):
                clip["sourceRef"] = asset_id
                tracks["image"]["clips"].append(clip)
            else:
                clip["sourceRef"] = asset_id
                tracks["video"]["clips"].append(clip)
        else:
            clip["content"] = scene["script"]
            clip["styleRef"] = "style://packaging/default"
            tracks["text"]["clips"].append(clip)

    for current, nxt in zip(storyboard, storyboard[1:]):
        start = current["endSec"]
        end = min(nxt["startSec"] + 0.18, max(nxt["startSec"], start + 0.18))
        tracks["transition"]["clips"].append(
            {
                "id": f"transition-{current['id']}-to-{nxt['id']}",
                "startSec": start,
                "endSec": end,
                "content": "quick-cut",
                "styleRef": "transition://default",
            }
        )

    ordered_tracks = [tracks[track_type] for track_type in TRACK_ORDER]
    timeline = {"durationSec": 0.0, "tracks": ordered_tracks}
    validation = validate_contract("render-timeline", timeline)
    if not validation.valid:
        raise ValueError(f"Invalid RenderTimeline payload: {validation.errors}")
    return timeline


def _type_score(*, required_types: set[str], asset: dict[str, Any], slot_is_visual: bool) -> float:
    if asset["type"] in required_types:
        return 1.0
    if slot_is_visual and asset["type"] == "text":
        return 0.5
    if "packaging" in required_types and asset["type"] == "text":
        return 1.0
    return 0.0


def _duration_score(
    *, slot_duration: float, asset: dict[str, Any], moments: list[dict[str, Any]]
) -> tuple[float, str | None]:
    if asset["type"] == "video":
        if moments:
            best = max(
                moments,
                key=lambda m: min(1.0, (float(m["endSec"]) - float(m["startSec"])) / slot_duration),
            )
            duration = float(best["endSec"]) - float(best["startSec"])
            return min(1.0, max(0.0, duration / slot_duration)), best["id"]
        duration = float(asset.get("durationSec", slot_duration))
        return min(1.0, max(0.0, duration / slot_duration)), None
    if asset["type"] == "image":
        return 0.7, None
    return 0.6, None


def _build_asset_tokens(asset: dict[str, Any]) -> list[str]:
    tags = list(asset.get("tags", []))
    description = str(asset.get("description", ""))
    return sorted(set(tags) | _tokenize(description))


def _tokenize(text: str) -> set[str]:
    lowered = text.lower()
    normalized = "".join(ch if ch.isalnum() else " " for ch in lowered)
    tokens = {token for token in normalized.split() if token}
    for keyword in KEYWORD_TOKENS:
        if keyword in lowered:
            tokens.add(keyword)
    return tokens


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _reason_text(type_score: float, semantic_score: float, duration_score: float) -> str:
    return (
        f"type={type_score:.2f}, semantic={semantic_score:.2f}, duration={duration_score:.2f}"
    )


def _impact_from_importance(importance: str) -> str:
    if importance == "must_have":
        return "high"
    if importance == "recommended":
        return "medium"
    return "low"


def _suggest_fixes(
    *,
    slot: dict[str, Any],
    visual_density: str,
    has_visual_partial: bool,
    inventory: dict[str, Any],
) -> list[str]:
    fixes: list[str] = []
    role = slot.get("role")
    slot_visual = bool({"video", "image"} & set(slot.get("requiredAssetType", [])))
    if slot_visual and has_visual_partial:
        fixes.append("asset_reuse")

    if role in {"benefit_card", "hook_text", "comparison"} or visual_density == "high":
        fixes.append("packaging_completion")

    if inventory.get("extractedFacts"):
        fixes.append("text_completion")

    ordered = []
    for item in ["asset_reuse", "packaging_completion", "text_completion"]:
        if item in fixes and item not in ordered:
            ordered.append(item)
    return ordered or ["text_completion"]


def _source_from_fix(strategy: str) -> str:
    if strategy == "asset_reuse":
        return "asset_reuse"
    if strategy == "packaging_completion":
        return "packaging_completion"
    if strategy == "text_completion":
        return "text_completion"
    return "generated"

