from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Callable

from app.agents.edit_intent_parser import run_edit_intent_parser
from app.pipelines.intent_applier import (
    PIPELINE_STAGE_ORDER,
    ReviseContext,
    apply_intents_to_context,
    build_source_summary,
    compute_affected_stages,
)
from app.pipelines.revise_scope import MaterialScope, material_scope_preserves_generated
from app.pipelines.revise_material_edit import (
    apply_narration_preview_to_storyboard,
    archive_slot_material,
    collect_seed_invalidate_plan,
    normalize_plan_storyboard_timing,
    rebind_plan_to_generation,
)
from app.pipelines.material_review import material_review_enabled, material_review_on_revise_enabled
from app.pipelines.material_review_revise import (
    material_review_revise_context_payload,
    reset_material_review_for_revise_fork,
)
from app.providers.completion_registry import invalidate_material_for_slots
from app.runtime.checkpoint import GenerationCheckpoint, generation_artifact_root

EmitFn = Callable[..., dict[str, Any]]

ARTIFACTS_BY_STAGE: dict[str, tuple[str, ...]] = {
    "analyzing_assets": ("asset-inventory.json",),
    "mapping_slots": ("slot-matches.json", "gap-report.json"),
    "drafting_master_script": ("script-draft.json",),
    "drafting_storyboard": ("script-draft.json",),
    "planning_completion": ("generation-plan.json",),
    "generating_material": ("material-state.json",),
    "building_timeline": (),
    "rendering": (),
}


def _stages_before(first_stage: str) -> list[str]:
    if first_stage not in PIPELINE_STAGE_ORDER:
        return []
    index = PIPELINE_STAGE_ORDER.index(first_stage)
    return list(PIPELINE_STAGE_ORDER[:index])


def _artifacts_to_clear_from(stage: str, *, material_scope: str = "all") -> set[str]:
    names: set[str] = set()
    if stage not in PIPELINE_STAGE_ORDER:
        return names
    index = PIPELINE_STAGE_ORDER.index(stage)
    for downstream in PIPELINE_STAGE_ORDER[index:]:
        names.update(ARTIFACTS_BY_STAGE.get(downstream, ()))
    if index <= PIPELINE_STAGE_ORDER.index("planning_completion"):
        names.add("generation-plan.json")
    if material_scope == "all" and index <= PIPELINE_STAGE_ORDER.index("generating_material"):
        names.add("generated")
    return names


def seed_revise_generation(
    *,
    project_root: Path,
    source_generation_id: str,
    target_generation_id: str,
    intents: list[dict[str, Any]],
    revise_context: ReviseContext,
    instruction: str | None = None,
) -> Path:
    source_root = generation_artifact_root(project_root, source_generation_id)
    target_root = generation_artifact_root(project_root, target_generation_id)
    if not source_root.is_dir():
        raise FileNotFoundError(f"Source generation artifacts not found: {source_root}")

    if target_root.exists():
        shutil.rmtree(target_root)
    shutil.copytree(source_root, target_root)

    affected = compute_affected_stages(intents)
    first_stage = affected[0] if affected else PIPELINE_STAGE_ORDER[-1]
    artifacts_to_clear = _artifacts_to_clear_from(
        first_stage,
        material_scope=revise_context.material_scope,
    )

    plan_path = target_root / "generation-plan.json"
    source_plan: dict[str, Any] | None = None
    if plan_path.is_file():
        source_plan = json.loads(plan_path.read_text(encoding="utf-8"))
        source_plan = rebind_plan_to_generation(
            source_plan,
            source_generation_id=source_generation_id,
            target_generation_id=target_generation_id,
        )
        affected_slot_set = set(revise_context.affected_slot_ids or [])
        if affected_slot_set:
            apply_narration_preview_to_storyboard(target_root, source_plan, affected_slot_set)
            normalize_plan_storyboard_timing(source_plan, affected_slot_set)
        snapshot: dict[str, Any] = {}
        if isinstance(source_plan.get("storyboard"), list):
            snapshot["storyboard"] = source_plan["storyboard"]
        if isinstance(source_plan.get("masterNarration"), str):
            snapshot["masterNarration"] = source_plan["masterNarration"]
        if isinstance(source_plan.get("packagingPlan"), dict):
            snapshot["packagingPlan"] = source_plan["packagingPlan"]
        if isinstance(source_plan.get("visualStyleBible"), dict):
            snapshot["visualStyleBible"] = source_plan["visualStyleBible"]
        if snapshot:
            (target_root / "revise-snapshot.json").write_text(
                json.dumps(snapshot, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

    material_edit_mode = "full"
    edit_instruction: str | None = None
    for intent in intents:
        if not isinstance(intent, dict):
            continue
        params = intent.get("params") if isinstance(intent.get("params"), dict) else {}
        raw_mode = str(params.get("materialEditMode") or "").strip()
        if raw_mode in {"edit", "full"}:
            material_edit_mode = raw_mode
        raw_instruction = str(params.get("editInstruction") or "").strip()
        if raw_instruction:
            edit_instruction = raw_instruction

    if revise_context.material_scope == "scoped" and revise_context.affected_slot_ids and source_plan:
        completion_actions = list(source_plan.get("completionActions") or [])
        generated_root = target_root / "generated"
        material_state_path = target_root / "material-state.json"
        if completion_actions and generated_root.is_dir():
            slot_id_set = set(revise_context.affected_slot_ids)
            if material_edit_mode == "edit":
                for slot_id in sorted(slot_id_set):
                    archive_slot_material(
                        generation_root=target_root,
                        generated_root=generated_root,
                        actions=completion_actions,
                        slot_id=slot_id,
                    )
            preserve_ids, slot_chain_kinds = collect_seed_invalidate_plan(
                actions=completion_actions,
                slot_ids=slot_id_set,
                material_edit_mode=material_edit_mode,
            )
            invalidate_material_for_slots(
                actions=completion_actions,
                generated_root=generated_root,
                slot_ids=slot_id_set,
                material_state_path=material_state_path,
                preserve_action_ids=preserve_ids,
            )
            source_plan["completionActions"] = completion_actions
            if "generation-plan.json" not in artifacts_to_clear:
                plan_path.write_text(
                    json.dumps(source_plan, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
        else:
            slot_chain_kinds = {}
    else:
        slot_chain_kinds = {}

    for artifact_name in artifacts_to_clear:
        artifact_path = target_root / artifact_name
        if artifact_path.is_file():
            artifact_path.unlink()
        elif artifact_path.is_dir():
            shutil.rmtree(artifact_path)

    if material_review_enabled() and material_review_on_revise_enabled():
        needs_material_review = "generating_material" in revise_context.affected_pipeline_stages
        if needs_material_review and revise_context.material_scope != "none":
            affected_slot_set = set(revise_context.affected_slot_ids or [])
            full_reset = revise_context.material_scope == "all" and not affected_slot_set
            reset_material_review_for_revise_fork(
                target_root,
                affected_slot_set,
                full_reset=full_reset,
            )

    revise_context_payload: dict[str, Any] = {
        "sourceGenerationId": source_generation_id,
        "instruction": instruction,
        "generationParams": revise_context.generation_params,
        "agentOverrides": revise_context.agent_overrides,
        "affectedStages": revise_context.affected_pipeline_stages,
        "rerunStoryboard": revise_context.rerun_storyboard,
        "rerunPackaging": revise_context.rerun_packaging,
        "affectedSceneIds": revise_context.affected_scene_ids,
        "affectedSlotIds": revise_context.affected_slot_ids,
        "materialScope": revise_context.material_scope,
        "preserveGenerated": revise_context.preserve_generated,
        "materialEditMode": material_edit_mode,
        "editInstruction": edit_instruction,
        "slotChainKinds": slot_chain_kinds,
    }
    revise_context_payload.update(
        material_review_revise_context_payload(
            source_generation_id=source_generation_id,
            revise_context=revise_context,
        )
    )

    (target_root / "edit-intent.json").write_text(
        json.dumps({"intents": intents}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (target_root / "revise-context.json").write_text(
        json.dumps(revise_context_payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    checkpoint = GenerationCheckpoint.load(target_root / "checkpoint.json")
    checkpoint.generationId = target_generation_id
    checkpoint.completedStages = _stages_before(first_stage)
    checkpoint.failedStage = None
    checkpoint.humanReviewMode = False
    checkpoint.save(target_root / "checkpoint.json")
    return target_root


def load_revise_context(generation_root: Path) -> ReviseContext | None:
    path = generation_root / "revise-context.json"
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    material_scope_raw = payload.get("materialScope") or "all"
    material_scope: MaterialScope = (
        material_scope_raw if material_scope_raw in {"none", "scoped", "all"} else "all"
    )
    return ReviseContext(
        generation_params=dict(payload.get("generationParams") or {}),
        agent_overrides=dict(payload.get("agentOverrides") or {}),
        affected_pipeline_stages=list(payload.get("affectedStages") or []),
        rerun_storyboard=bool(payload.get("rerunStoryboard", True)),
        rerun_packaging=bool(payload.get("rerunPackaging", True)),
        affected_scene_ids=list(payload.get("affectedSceneIds") or []),
        affected_slot_ids=list(payload.get("affectedSlotIds") or []),
        material_scope=material_scope,
        preserve_generated=bool(
            payload.get("preserveGenerated", material_scope_preserves_generated(material_scope))
        ),
    )


def load_revise_snapshot(generation_root: Path) -> dict[str, Any] | None:
    path = generation_root / "revise-snapshot.json"
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def is_revise_generation(generation_root: Path) -> bool:
    if (generation_root / "edit-intent.json").is_file():
        return True
    if (generation_root / "revise-snapshot.json").is_file():
        return True
    return (generation_root / "revise-context.json").is_file()


def merge_agent_overrides(
    variant: str,
    agent_name: str,
    revise_context: ReviseContext | None,
) -> dict[str, Any]:
    from app.config.variants import load_agent_overrides

    merged = dict(load_agent_overrides(variant, agent_name))
    if revise_context is None:
        return merged
    merged.update(revise_context.agent_overrides.get(agent_name, {}))
    return merged


def parse_instruction_intents(
    runner: Any,
    *,
    instruction: str,
    source_plan: dict[str, Any],
    context: Any,
    generation_id: str,
    pre_parsed_intents: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    if pre_parsed_intents is not None:
        return list(pre_parsed_intents)
    source_summary = build_source_summary(source_plan)
    payload = run_edit_intent_parser(
        runner,
        instruction=instruction,
        source_summary=source_summary,
        context=context,
        generation_id=generation_id,
    )
    intents = payload.get("intents")
    if not isinstance(intents, list) or not intents:
        raise ValueError("EditIntentParser returned no intents")
    return intents
