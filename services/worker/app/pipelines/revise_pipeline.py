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
from app.runtime.checkpoint import GenerationCheckpoint, generation_artifact_root

EmitFn = Callable[..., dict[str, Any]]

ARTIFACTS_BY_STAGE: dict[str, tuple[str, ...]] = {
    "analyzing_assets": ("asset-inventory.json",),
    "mapping_slots": ("slot-matches.json",),
    "planning_completion": ("gap-report.json", "generation-plan.json"),
    "generating_material": ("material-state.json",),
    "building_timeline": (),
    "rendering": (),
}


def _stages_before(first_stage: str) -> list[str]:
    if first_stage not in PIPELINE_STAGE_ORDER:
        return []
    index = PIPELINE_STAGE_ORDER.index(first_stage)
    return list(PIPELINE_STAGE_ORDER[:index])


def _artifacts_to_clear_from(stage: str) -> set[str]:
    names: set[str] = set()
    if stage not in PIPELINE_STAGE_ORDER:
        return names
    index = PIPELINE_STAGE_ORDER.index(stage)
    for downstream in PIPELINE_STAGE_ORDER[index:]:
        names.update(ARTIFACTS_BY_STAGE.get(downstream, ()))
    if index <= PIPELINE_STAGE_ORDER.index("planning_completion"):
        names.add("generation-plan.json")
    if index <= PIPELINE_STAGE_ORDER.index("generating_material"):
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

    plan_path = target_root / "generation-plan.json"
    if plan_path.is_file():
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        snapshot: dict[str, Any] = {}
        if isinstance(plan.get("storyboard"), list):
            snapshot["storyboard"] = plan["storyboard"]
        if isinstance(plan.get("packagingPlan"), dict):
            snapshot["packagingPlan"] = plan["packagingPlan"]
        if snapshot:
            (target_root / "revise-snapshot.json").write_text(
                json.dumps(snapshot, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

    for artifact_name in _artifacts_to_clear_from(first_stage):
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
    checkpoint.save(target_root / "checkpoint.json")
    return target_root


def load_revise_context(generation_root: Path) -> ReviseContext | None:
    path = generation_root / "revise-context.json"
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return ReviseContext(
        generation_params=dict(payload.get("generationParams") or {}),
        agent_overrides=dict(payload.get("agentOverrides") or {}),
        affected_pipeline_stages=list(payload.get("affectedStages") or []),
        rerun_storyboard=bool(payload.get("rerunStoryboard", True)),
        rerun_packaging=bool(payload.get("rerunPackaging", True)),
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
