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
from app.runtime.video_gen_quota import VideoGenQuota, provisional_gap_report
from app.tools.image_gen_tool import ToolError
from app.pipelines.generation_strategy import is_short_form_strategy, resolve_generation_strategy
from app.pipelines.script_draft import (
    empty_script_draft,
    load_script_draft,
    master_is_approved,
    save_script_draft,
    storyboard_is_approved,
)
from app.pipelines.short_form_direct import (
    filter_short_form_completion_actions,
    simplify_storyboard_for_short_form,
)
from app.pipelines.duration_target import normalize_duration_target
from app.pipelines.asset_understanding import run_asset_understanding
from app.pipelines.user_brief import build_baseline_extracted_facts, normalize_user_brief
from app.pipelines.master_narration import apply_master_narration_to_storyboard, derive_master_from_storyboard
from app.pipelines.revise_pipeline import load_revise_snapshot, merge_agent_overrides
from app.agents.packaging_designer import run_packaging_designer
from app.agents.runner import AgentRunner
from app.agents.slot_mapper import classify_slot_matches, run_slot_mapper
from app.agents.storyboard_writer import run_storyboard_writer
from app.runtime.task_context import TaskContext
from app.validation.schema_loader import validate_contract

TRACK_ORDER = ["video", "image", "text", "effect", "transition", "voiceover", "bgm"]


def build_narration_actions(
    storyboard: list[dict[str, Any]],
    *,
    skip_slot_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Add TTS completion actions for scenes with non-empty script (independent of visual gap)."""
    skipped = skip_slot_ids or set()
    actions: list[dict[str, Any]] = []
    for scene in storyboard:
        if not isinstance(scene, dict):
            continue
        slot_id = str(scene.get("slotId", ""))
        if not slot_id or slot_id in skipped:
            continue
        script = str(scene.get("script", "")).strip()
        if not script:
            continue
        actions.append(
            {
                "id": f"action-{slot_id}-tts",
                "slotId": slot_id,
                "strategy": "tts",
                "provider": "tts",
                "reason": "分镜口播合成",
                "rationale": "分镜口播合成",
                "outputRef": f"completion://{slot_id}/tts",
            }
        )
    return actions


def merge_script_subtitles_into_timeline(
    timeline: dict[str, Any],
    storyboard: list[dict[str, Any]],
    packaging_plan: dict[str, Any],
) -> dict[str, Any]:
    """Append subtitle clips from storyboard.script; voiceover clips are filled after TTS."""
    preset = "clean"
    subtitle = packaging_plan.get("subtitle")
    if isinstance(subtitle, dict) and subtitle.get("preset"):
        preset = str(subtitle["preset"])
    style_ref = f"style://subtitle/{preset}"

    tracks = timeline.get("tracks", [])
    if not isinstance(tracks, list):
        return timeline

    text_track: dict[str, Any] | None = None
    for track in tracks:
        if isinstance(track, dict) and track.get("type") == "text":
            text_track = track
            break
    if text_track is None:
        text_track = {"id": "track-text", "type": "text", "clips": []}
        tracks.append(text_track)

    clips = text_track.setdefault("clips", [])
    existing_ids = {
        str(clip.get("id", ""))
        for clip in clips
        if isinstance(clip, dict)
    }

    for scene in storyboard:
        if not isinstance(scene, dict):
            continue
        slot_id = str(scene.get("slotId", ""))
        script = str(scene.get("script", "")).strip()
        if not slot_id or not script:
            continue
        subtitle_id = f"subtitle-{slot_id}"
        if subtitle_id in existing_ids:
            continue
        clips.append(
            {
                "id": subtitle_id,
                "startSec": float(scene["startSec"]),
                "endSec": float(scene["endSec"]),
                "content": script,
                "styleRef": style_ref,
            }
        )
        existing_ids.add(subtitle_id)

    validation = validate_contract("render-timeline", timeline)
    if not validation.valid:
        raise ValueError(f"Invalid RenderTimeline payload: {validation.errors}")
    return timeline


def build_asset_inventory(
    *,
    project_id: str,
    user_brief: dict[str, Any],
    assets: list[dict[str, Any]],
) -> dict[str, Any]:
    brief = normalize_user_brief(user_brief)

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

    extracted_facts = build_baseline_extracted_facts(brief)

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
        "userBrief": brief,
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
    knowledge_context: dict[str, Any] | None = None,
    database_path: Path | None = None,
    sample_analysis: dict[str, Any] | None = None,
    gateway_store: Any | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    if inventory is None:
        if inventory_baseline is None:
            raise ValueError("inventory_baseline or inventory is required")
        inventory = run_asset_understanding(
            runner,
            inventory=inventory_baseline,
            context=context,
            generation_id=generation_id,
            video_structure=structure,
            gateway_store=gateway_store,
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
            knowledge_context=knowledge_context,
        )
        _, weak_ids, _missing_ids = classify_slot_matches(structure, resolved_slot_matches)
        if database_path is not None and len(weak_ids) >= 2 and knowledge_context is not None:
            from app.knowledge.context_resolver import resolve_knowledge_context

            knowledge_context = resolve_knowledge_context(
                storage_root=context.storage_root,
                database_path=database_path,
                project_id=context.project_id,
                level=1,
                weak_slot_count=len(weak_ids),
                video_structure=structure,
                sample_analysis=sample_analysis,
            )
        context.emit_event(
            stage="planning_completion",
            progress=45,
            message="Planning gap completion providers",
        )
        planning_gap_report = provisional_gap_report(structure, resolved_slot_matches)
        video_quota = VideoGenQuota.from_structure(
            structure,
            gap_report=planning_gap_report,
        )
        resolved_gap_report = run_gap_planner(
            runner,
            structure=structure,
            inventory=inventory,
            slot_matches=resolved_slot_matches,
            context=context,
            generation_id=generation_id,
            variant=variant,
            quota=video_quota,
            knowledge_context=knowledge_context,
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
        knowledge_context=knowledge_context,
    )


def run_mapping_and_gap(
    runner: AgentRunner,
    *,
    structure: dict[str, Any],
    inventory: dict[str, Any],
    context: TaskContext,
    generation_id: str,
    variant: str = "default",
    revise_context: ReviseContext | None = None,
    knowledge_context: dict[str, Any] | None = None,
    database_path: Path | None = None,
    sample_analysis: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any] | None]:
    context.emit_event(
        stage="mapping_slots",
        progress=35,
        message="Mapping structure slots to user assets",
    )
    slot_matches = run_slot_mapper(
        runner,
        structure=structure,
        inventory=inventory,
        context=context,
        generation_id=generation_id,
        variant_overrides=merge_agent_overrides(variant, "slot_mapper", revise_context),
        knowledge_context=knowledge_context,
    )
    resolved_knowledge = knowledge_context
    _, weak_ids, _missing_ids = classify_slot_matches(structure, slot_matches)
    if database_path is not None and len(weak_ids) >= 2 and knowledge_context is not None:
        from app.knowledge.context_resolver import resolve_knowledge_context

        resolved_knowledge = resolve_knowledge_context(
            storage_root=context.storage_root,
            database_path=database_path,
            project_id=context.project_id,
            level=1,
            weak_slot_count=len(weak_ids),
            video_structure=structure,
            sample_analysis=sample_analysis,
        )
    context.emit_event(
        stage="planning_completion",
        progress=45,
        message="Planning gap completion providers",
    )
    planning_gap_report = provisional_gap_report(structure, slot_matches)
    video_quota = VideoGenQuota.from_structure(
        structure,
        gap_report=planning_gap_report,
    )
    gap_report = run_gap_planner(
        runner,
        structure=structure,
        inventory=inventory,
        slot_matches=slot_matches,
        context=context,
        generation_id=generation_id,
        variant=variant,
        quota=video_quota,
        knowledge_context=resolved_knowledge,
    )
    return slot_matches, gap_report, resolved_knowledge


def draft_master_script(
    runner: AgentRunner,
    *,
    structure: dict[str, Any],
    inventory: dict[str, Any],
    gap_report: dict[str, Any],
    context: TaskContext,
    generation_id: str,
    generation_root: Path,
    variant: str,
    duration_target: dict[str, Any],
    knowledge_context: dict[str, Any] | None = None,
    revise_context: ReviseContext | None = None,
) -> dict[str, Any]:
    context.emit_event(
        stage="drafting_master_script",
        progress=46,
        message="Drafting master narration script",
    )
    writer_output = run_storyboard_writer(
        runner,
        structure=structure,
        inventory=inventory,
        gap_report=gap_report,
        context=context,
        generation_id=generation_id,
        variant=variant,
        agent_overrides=merge_agent_overrides(variant, "storyboard_writer", revise_context),
        knowledge_context=knowledge_context,
        phase="master_only",
        duration_target=duration_target,
    )
    draft = load_script_draft(generation_root) or empty_script_draft(
        generation_id=generation_id,
        project_id=str(inventory.get("projectId", context.project_id)),
        variant=variant,
        duration_target_sec=float(duration_target.get("targetSec", 0.0)),
    )
    draft["masterNarration"] = str(writer_output.get("masterNarration") or "")
    draft["masterNarrationStatus"] = "draft"
    draft["storyboard"] = []
    draft["storyboardStatus"] = "draft"
    draft["generationStrategy"] = resolve_generation_strategy(float(duration_target.get("targetSec", 30.0)))
    draft["durationTargetSec"] = float(duration_target.get("targetSec", 30.0))
    return save_script_draft(generation_root, draft)


def draft_storyboard_script(
    runner: AgentRunner,
    *,
    structure: dict[str, Any],
    inventory: dict[str, Any],
    gap_report: dict[str, Any],
    context: TaskContext,
    generation_id: str,
    generation_root: Path,
    variant: str,
    duration_target: dict[str, Any],
    knowledge_context: dict[str, Any] | None = None,
    revise_context: ReviseContext | None = None,
) -> dict[str, Any]:
    draft = load_script_draft(generation_root)
    if draft is None or not master_is_approved(draft):
        raise ValueError("Master narration must be approved before drafting storyboard")
    context.emit_event(
        stage="drafting_storyboard",
        progress=50,
        message="Drafting storyboard scenes from approved master script",
    )
    writer_output = run_storyboard_writer(
        runner,
        structure=structure,
        inventory=inventory,
        gap_report=gap_report,
        context=context,
        generation_id=generation_id,
        variant=variant,
        agent_overrides=merge_agent_overrides(variant, "storyboard_writer", revise_context),
        knowledge_context=knowledge_context,
        phase="storyboard_from_master",
        master_narration=str(draft.get("masterNarration") or ""),
        duration_target=duration_target,
    )
    draft = dict(draft)
    draft["storyboard"] = list(writer_output.get("storyboard") or [])
    draft["storyboardStatus"] = "draft"
    return save_script_draft(generation_root, draft)


def run_planning_from_script_draft(
    runner: AgentRunner,
    *,
    structure: dict[str, Any],
    inventory: dict[str, Any],
    slot_matches: list[dict[str, Any]],
    gap_report: dict[str, Any],
    context: TaskContext,
    generation_id: str,
    generation_root: Path,
    variant: str = "default",
    revise_context: ReviseContext | None = None,
    knowledge_context: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    draft = load_script_draft(generation_root)
    if draft is None or not storyboard_is_approved(draft):
        raise ValueError("Storyboard must be approved before planning completion")
    master_narration = str(draft.get("masterNarration") or "")
    storyboard = [dict(scene) for scene in draft.get("storyboard") or [] if isinstance(scene, dict)]
    strategy = str(
        draft.get("generationStrategy")
        or resolve_generation_strategy(
            float(draft.get("durationTargetSec") or structure.get("metadata", {}).get("durationSec", 30.0))
        )
    )
    target_sec = float(
        draft.get("durationTargetSec")
        or structure.get("metadata", {}).get("durationSec", 30.0)
    )
    if is_short_form_strategy(strategy):
        storyboard = simplify_storyboard_for_short_form(
            storyboard,
            target_sec=target_sec,
        )

    snapshot = load_revise_snapshot(generation_root)
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
        master_narration=master_narration,
        generation_strategy=strategy,
        duration_target_sec=target_sec,
    )
    return inventory, slot_matches, gap_report, plan


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
    knowledge_context: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    snapshot = load_revise_snapshot(generation_root) if generation_root is not None else None

    storyboard: list[dict[str, Any]]
    master_narration = ""
    if revise_context is not None and not revise_context.rerun_storyboard and snapshot:
        storyboard = list(snapshot.get("storyboard") or [])
        master_narration = str(snapshot.get("masterNarration") or "")
        if storyboard and not master_narration.strip():
            master_narration, storyboard = apply_master_narration_to_storyboard(
                master_narration="",
                storyboard=storyboard,
                structure=structure,
            )
    else:
        context.emit_event(
            stage="planning_completion",
            progress=48,
            message="Writing storyboard scenes",
        )
        writer_output = run_storyboard_writer(
            runner,
            structure=structure,
            inventory=inventory,
            gap_report=gap_report,
            context=context,
            generation_id=generation_id,
            variant=variant,
            agent_overrides=merge_agent_overrides(variant, "storyboard_writer", revise_context),
            knowledge_context=knowledge_context,
        )
        master_narration = str(writer_output.get("masterNarration") or "")
        storyboard = list(writer_output.get("storyboard") or [])

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
        master_narration=master_narration,
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
    master_narration: str | None = None,
    generation_strategy: str | None = None,
    duration_target_sec: float | None = None,
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

    visual_actions: list[dict[str, Any]] = []
    for scene in storyboard:
        slot_id = scene["slotId"]
        if slot_id not in gap_by_slot:
            continue
        slot_gap = gap_by_slot[slot_id]
        fixes = list(slot_gap.get("suggestedFixes", [])) or ["hyperframes_material"]
        for index, strategy in enumerate(fixes):
            if index == 0:
                action_id = f"action-{slot_id}"
            elif strategy == "hyperframes_material" and fixes[0] == "stock_media_search":
                action_id = f"action-{slot_id}-ken-burns"
            else:
                action_id = f"action-{slot_id}-chain-{index}"
            visual_actions.append(
                {
                    "id": action_id,
                    "slotId": slot_id,
                    "strategy": strategy,
                    "provider": strategy,
                    "reason": slot_gap["reason"],
                    "rationale": slot_gap["reason"],
                    "outputRef": f"completion://{slot_id}/{strategy}",
                }
            )

    tts_from_gap = {
        str(action["slotId"])
        for action in visual_actions
        if str(action.get("provider") or action.get("strategy", "")) == "tts"
    }
    narration_actions = build_narration_actions(storyboard, skip_slot_ids=tts_from_gap)
    completion_actions = visual_actions + narration_actions

    resolved_strategy = generation_strategy or resolve_generation_strategy(
        float(
            duration_target_sec
            if duration_target_sec is not None
            else structure.get("metadata", {}).get("durationSec", 30.0)
        )
    )
    if is_short_form_strategy(resolved_strategy) and storyboard:
        primary_slot = str(storyboard[0].get("slotId") or "")
        completion_actions = filter_short_form_completion_actions(
            completion_actions,
            primary_slot_id=primary_slot,
        )

    timeline = _build_timeline(
        storyboard=storyboard,
        slot_matches=matches_by_slot,
        slots=slots_by_id,
        asset_type_by_id=asset_type_by_id,
    )
    duration = max((scene["endSec"] for scene in storyboard), default=0.0)
    timeline["durationSec"] = duration
    timeline = merge_script_subtitles_into_timeline(
        timeline,
        storyboard,
        packaging_plan,
    )

    master = str(master_narration or "").strip() or derive_master_from_storyboard(storyboard)

    plan = {
        "id": f"generation-plan-{structure['projectId']}",
        "projectId": structure["projectId"],
        "structureId": structure["id"],
        "inventoryId": inventory["id"],
        "gapReportId": gap_report["id"],
        "variant": variant,
        "generationStrategy": resolved_strategy,
        "masterNarration": master,
        "storyboard": storyboard,
        "timeline": timeline,
        "packagingPlan": packaging_plan,
        "completionActions": completion_actions,
    }
    if duration_target_sec is not None:
        plan["durationTargetSec"] = round(float(duration_target_sec), 2)
    validation = validate_contract("generation-plan", plan)
    if not validation.valid:
        raise ValueError(f"Invalid GenerationPlan payload: {validation.errors}")
    return plan


ProgressEmitter = Callable[[str, str], None]
ArtifactRegistrar = Callable[[str, str | Path], dict[str, Any]]


class FixtureMaterialGateway:
    """Deterministic media responses for fixture/demo runs without live APIs."""

    is_fixture = True

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


def is_fixture_material_gateway(gateway: Any) -> bool:
    """True when material completion should use deterministic fixture stubs."""
    return isinstance(gateway, FixtureMaterialGateway)


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
    gap_report: dict[str, Any] | None = None,
    runner: AgentRunner | None = None,
    task_context: TaskContext | None = None,
    variant_overrides: dict[str, Any] | None = None,
    brand_colors: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    actions = filter_aigc_completion_actions(plan.get("completionActions", []))
    generated_root = generation_root / "generated"
    generated_root.mkdir(parents=True, exist_ok=True)
    state_path = material_state_path or (generation_root / "material-state.json")
    if state_path.is_file():
        quota, completed_ids = load_material_state(state_path)
    else:
        report = gap_report or provisional_gap_report(structure, slot_matches)
        quota = VideoGenQuota.from_structure(structure, gap_report=report)
        completed_ids = set()
        save_material_state(
            state_path,
            quota=quota,
            completed_action_ids=completed_ids,
        )

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
        elif scene.get("source") == "generated":
            visual = str(scene.get("visual", "")).strip()
            lowered = visual.lower()
            if lowered.endswith((".mp4", ".webm", ".mov", ".mkv")):
                clip["sourceRef"] = visual
                tracks["video"]["clips"].append(clip)
            elif lowered.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp")):
                clip["sourceRef"] = visual
                tracks["image"]["clips"].append(clip)
            elif "image" in slot.get("requiredAssetType", []) and "video" not in slot.get(
                "requiredAssetType", []
            ):
                tracks["image"]["clips"].append(clip)
            else:
                tracks["video"]["clips"].append(clip)
        else:
            if "image" in slot.get("requiredAssetType", []) and "video" not in slot.get(
                "requiredAssetType", []
            ):
                tracks["image"]["clips"].append(clip)
            else:
                tracks["video"]["clips"].append(clip)

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
