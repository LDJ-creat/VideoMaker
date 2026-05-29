from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from app.agents.gap_planner import run_gap_planner
from app.gateway.model_gateway import ModelGateway
from app.gateway.providers.pluggable_video import VideoJobResult
from app.providers.completion_registry import (
    MaterialContext,
    action_artifact_satisfied,
    apply_material_results_to_plan,
    execute_completion_plan,
    filter_aigc_completion_actions,
    load_material_state,
    register_default_providers,
    save_material_state,
)
from app.runtime.video_gen_quota import VideoGenQuota
from app.tools.image_gen_tool import ToolError
from app.pipelines.asset_understanding import run_asset_understanding
from app.pipelines.intent_applier import ReviseContext
from app.pipelines.revise_pipeline import load_revise_snapshot, merge_agent_overrides
from app.agents.packaging_designer import run_packaging_designer
from app.agents.runner import AgentRunner
from app.agents.slot_mapper import run_slot_mapper
from app.agents.storyboard_writer import run_storyboard_writer
from app.runtime.task_context import TaskContext
from app.validation.schema_loader import validate_contract

TRACK_ORDER = ["video", "image", "text", "effect", "transition", "voiceover", "bgm"]


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
                    "tags": list(asset.get("tags", [])),
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


def run_agent_generation(
    runner: AgentRunner,
    *,
    structure: dict[str, Any],
    inventory_baseline: dict[str, Any] | None = None,
    inventory: dict[str, Any] | None = None,
    context: TaskContext,
    generation_id: str,
    variant: str = "default",
    revise_context: ReviseContext | None = None,
    slot_matches: list[dict[str, Any]] | None = None,
    gap_report: dict[str, Any] | None = None,
    skip_slot_mapping: bool = False,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    if inventory is None:
        if inventory_baseline is None:
            raise ValueError("inventory_baseline or inventory is required")
        inventory = run_asset_understanding(
            runner,
            inventory=inventory_baseline,
            context=context,
            generation_id=generation_id,
        )

    if skip_slot_mapping:
        if slot_matches is None:
            raise ValueError("slot_matches is required when skip_slot_mapping is True")
        if gap_report is None:
            raise ValueError("gap_report is required when skip_slot_mapping is True")
        resolved_slot_matches = slot_matches
        resolved_gap_report = gap_report
    else:
        context.emit_event(
            stage="mapping_slots",
            progress=35,
            message="Mapping structure slots to user assets",
        )
        resolved_slot_matches = run_slot_mapper(
            runner,
            structure=structure,
            inventory=inventory,
            context=context,
            generation_id=generation_id,
            variant_overrides=merge_agent_overrides(variant, "slot_mapper", revise_context),
        )
        context.emit_event(
            stage="planning_completion",
            progress=45,
            message="Planning gap completion providers",
        )
        resolved_gap_report = run_gap_planner(
            runner,
            structure=structure,
            inventory=inventory,
            slot_matches=resolved_slot_matches,
            context=context,
            generation_id=generation_id,
            variant=variant,
            quota=VideoGenQuota(max_calls=1),
        )

    return run_planning_completion(
        runner,
        structure=structure,
        inventory=inventory,
        slot_matches=resolved_slot_matches,
        gap_report=resolved_gap_report,
        context=context,
        generation_id=generation_id,
        variant=variant,
        revise_context=revise_context,
    )


def run_planning_completion(
    runner: AgentRunner,
    *,
    structure: dict[str, Any],
    inventory: dict[str, Any],
    slot_matches: list[dict[str, Any]],
    gap_report: dict[str, Any],
    context: TaskContext,
    generation_id: str,
    variant: str = "default",
    revise_context: ReviseContext | None = None,
    generation_root: Path | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    snapshot = load_revise_snapshot(generation_root) if generation_root is not None else None

    storyboard: list[dict[str, Any]]
    if revise_context is not None and not revise_context.rerun_storyboard and snapshot:
        storyboard = list(snapshot.get("storyboard") or [])
    else:
        context.emit_event(
            stage="planning_completion",
            progress=48,
            message="Writing storyboard scenes",
        )
        storyboard = run_storyboard_writer(
            runner,
            structure=structure,
            inventory=inventory,
            gap_report=gap_report,
            context=context,
            generation_id=generation_id,
            variant=variant,
            agent_overrides=merge_agent_overrides(variant, "storyboard_writer", revise_context),
        )

    packaging_plan: dict[str, Any]
    if revise_context is not None and not revise_context.rerun_packaging and snapshot:
        packaging_plan = dict(snapshot.get("packagingPlan") or {})
    else:
        context.emit_event(
            stage="planning_completion",
            progress=55,
            message="Designing packaging plan",
        )
        packaging_plan = run_packaging_designer(
            runner,
            structure=structure,
            storyboard=storyboard,
            context=context,
            generation_id=generation_id,
            variant=variant,
            agent_overrides=merge_agent_overrides(variant, "packaging_designer", revise_context),
        )

    plan = assemble_generation_plan(
        structure=structure,
        inventory=inventory,
        gap_report=gap_report,
        slot_matches=slot_matches,
        storyboard=storyboard,
        packaging_plan=packaging_plan,
        variant=variant,
    )
    return inventory, slot_matches, gap_report, plan


def assemble_generation_plan(
    *,
    structure: dict[str, Any],
    inventory: dict[str, Any],
    gap_report: dict[str, Any],
    slot_matches: list[dict[str, Any]],
    storyboard: list[dict[str, Any]],
    packaging_plan: dict[str, Any],
    variant: str = "default",
) -> dict[str, Any]:
    slots_by_id = {slot["id"]: slot for slot in structure.get("slots", [])}
    matches_by_slot = {match["slotId"]: match for match in slot_matches}
    asset_type_by_id = {
        asset["id"]: asset.get("type")
        for asset in inventory.get("assets", [])
        if isinstance(asset, dict) and asset.get("id")
    }
    gap_by_slot = {
        item["slotId"]: item
        for item in [*gap_report.get("weakSlots", []), *gap_report.get("missingSlots", [])]
    }

    completion_actions = []
    for scene in storyboard:
        slot_id = scene["slotId"]
        if slot_id not in gap_by_slot:
            continue
        slot_gap = gap_by_slot[slot_id]
        fixes = list(slot_gap.get("suggestedFixes", []))
        strategy = fixes[0] if fixes else "hyperframes_material"
        completion_actions.append(
            {
                "id": f"action-{slot_id}",
                "slotId": slot_id,
                "strategy": strategy,
                "provider": strategy,
                "reason": slot_gap["reason"],
                "rationale": slot_gap["reason"],
                "outputRef": f"completion://{slot_id}/{strategy}",
            }
        )

    timeline = _build_timeline(
        storyboard=storyboard,
        slot_matches=matches_by_slot,
        slots=slots_by_id,
        asset_type_by_id=asset_type_by_id,
    )
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
        "packagingPlan": packaging_plan,
        "completionActions": completion_actions,
    }
    validation = validate_contract("generation-plan", plan)
    if not validation.valid:
        raise ValueError(f"Invalid GenerationPlan payload: {validation.errors}")
    return plan


ProgressEmitter = Callable[[str, str], None]
ArtifactRegistrar = Callable[[str, str | Path], dict[str, Any]]


class FixtureMaterialGateway:
    """Deterministic media responses for fixture/demo runs without live APIs."""

    def generate_image(self, prompt: str, *, options: dict[str, Any] | None = None) -> bytes:
        _ = prompt, options
        return b"\x89PNG\r\n\x1a\n\x00"

    def synthesize_speech(self, text: str, *, options: dict[str, Any] | None = None) -> bytes:
        _ = text, options
        return b"RIFF----WAVEfmt "

    def submit_video_job(self, prompt: str, *, options: dict[str, Any] | None = None) -> str:
        _ = prompt, options
        return "fixture-video-job"

    def poll_video_job(self, job_id: str) -> VideoJobResult:
        return VideoJobResult(
            status="succeeded",
            job_id=job_id,
            video_bytes=b"fixture-mp4-bytes",
        )


def is_material_stage_done(
    generation_root: Path,
    plan: dict[str, Any],
) -> bool:
    actions = filter_aigc_completion_actions(plan.get("completionActions", []))
    if not actions:
        return True
    generated_root = generation_root / "generated"
    for action in actions:
        if not action_artifact_satisfied(action, generated_root):
            return False
    return True


def run_generating_material(
    *,
    plan: dict[str, Any],
    inventory: dict[str, Any],
    slot_matches: list[dict[str, Any]],
    structure: dict[str, Any],
    generation_root: Path,
    render_root: Path,
    gateway: ModelGateway | FixtureMaterialGateway,
    emit_progress: ProgressEmitter,
    register_artifact: ArtifactRegistrar,
    material_state_path: Path | None = None,
    runner: AgentRunner | None = None,
    task_context: TaskContext | None = None,
    variant_overrides: dict[str, Any] | None = None,
    brand_colors: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    actions = filter_aigc_completion_actions(plan.get("completionActions", []))
    generated_root = generation_root / "generated"
    generated_root.mkdir(parents=True, exist_ok=True)
    state_path = material_state_path or (generation_root / "material-state.json")
    quota, completed_ids = load_material_state(state_path)

    ctx = MaterialContext(
        project_id=str(plan.get("projectId", "")),
        generation_id=str(plan.get("id", "")),
        render_root=render_root,
        generated_root=generated_root,
        gateway=gateway,  # type: ignore[arg-type]
        quota=quota,
        inventory=inventory,
        slot_matches=slot_matches,
        storyboard=list(plan.get("storyboard", [])),
        structure=structure,
        emit_progress=emit_progress,
        register_artifact=register_artifact,
        completed_action_ids=set(completed_ids),
        runner=runner,
        task_context=task_context,
        variant_overrides=dict(variant_overrides or {}),
        brand_colors=dict(brand_colors or {}),
    )
    register_default_providers(ctx)

    pending = [
        action
        for action in actions
        if not (
            str(action["id"]) in ctx.completed_action_ids
            and action_artifact_satisfied(action, generated_root)
        )
    ]
    if not pending:
        return plan, []

    results = execute_completion_plan(pending, ctx, fail_fast=True)
    failed = next((item for item in results if not item.get("ok")), None)
    if failed is not None:
        error = failed.get("error") or {}
        raise ToolError(
            code=str(error.get("code", "material_failed")),
            message=str(error.get("message", "Material completion failed")),
            retryable=bool(error.get("retryable", False)),
        )

    updated_plan = apply_material_results_to_plan(plan, results=results, render_root=render_root)
    save_material_state(
        state_path,
        quota=ctx.quota,
        completed_action_ids=ctx.completed_action_ids,
    )
    return updated_plan, results


def _build_timeline(
    *,
    storyboard: list[dict[str, Any]],
    slot_matches: dict[str, dict[str, Any]],
    slots: dict[str, dict[str, Any]],
    asset_type_by_id: dict[str, str | None],
) -> dict[str, Any]:
    tracks = {
        track_type: {"id": f"track-{track_type}", "type": track_type, "clips": []}
        for track_type in TRACK_ORDER
    }

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
            asset_type = asset_type_by_id.get(asset_id)
            if match.get("momentId"):
                clip["sourceRef"] = str(match["momentId"])
                tracks["video"]["clips"].append(clip)
            elif asset_type == "image":
                clip["sourceRef"] = asset_id
                tracks["image"]["clips"].append(clip)
            elif asset_type == "video":
                clip["sourceRef"] = asset_id
                tracks["video"]["clips"].append(clip)
            elif asset_type == "text":
                clip["content"] = scene["script"]
                clip["styleRef"] = "style://packaging/default"
                tracks["text"]["clips"].append(clip)
            else:
                clip["sourceRef"] = asset_id
                if "image" in slot.get("requiredAssetType", []):
                    tracks["image"]["clips"].append(clip)
                else:
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
