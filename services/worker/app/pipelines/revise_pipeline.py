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

    if revise_context.material_scope == "scoped" and revise_context.affected_slot_ids and source_plan:
        completion_actions = list(source_plan.get("completionActions") or [])
        generated_root = target_root / "generated"
        material_state_path = target_root / "material-state.json"
        if completion_actions and generated_root.is_dir():
            invalidate_material_for_slots(
                actions=completion_actions,
                generated_root=generated_root,
                slot_ids=set(revise_context.affected_slot_ids),
                material_state_path=material_state_path,
            )
            source_plan["completionActions"] = completion_actions
            if "generation-plan.json" not in artifacts_to_clear:
                plan_path.write_text(
                    json.dumps(source_plan, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )

    for artifact_name in artifacts_to_clear:
        artifact_path = target_root / artifact_name
        if artifact_path.is_file():
            artifact_path.unlink()
        elif artifact_path.is_dir():
            shutil.rmtree(artifact_path)

    (target_root / "edit-intent.json").write_text(
        json.dumps({"intents": intents}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (target_root / "revise-context.json").write_text(
        json.dumps(
            {
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
            },
            indent=2,
            ensure_ascii=False,
        ),
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
