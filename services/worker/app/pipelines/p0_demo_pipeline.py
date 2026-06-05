from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from app.agents.prompt_loader import PromptLoader
from app.agents.runner import AgentRunner
from app.pipelines.structure_analysis_pipeline import run_structure_analysis_pipeline
from app.perception.sample_facts import (
    merge_visual_facts_into_sample_analysis,
    persist_sample_analysis,
    run_visual_facts_extraction,
)
from app.agents.structure_inputs import KeyframeEncodingError
from app.agents.failure_debug import tool_error_from_agent_failure
from app.config.variants import load_variant_gap_planner_overrides
from model_gateway.fixture import is_fixture_mode
from model_gateway.store import ModelGatewayStore

from app.gateway.model_gateway import ModelGateway
from app.pipelines.generation_pipeline import (
    FixtureMaterialGateway,
    build_asset_inventory,
    is_fixture_material_gateway,
    is_material_stage_done,
    run_agent_generation,
    run_generating_material,
    run_planning_completion,
)
from app.tools.image_gen_tool import ToolError
from app.pipelines.asset_understanding import run_asset_understanding
from app.pipelines.intent_applier import apply_intents_to_context
from app.pipelines.revise_pipeline import (
    load_revise_context,
    parse_instruction_intents,
    seed_revise_generation,
)
from app.knowledge.context_resolver import resolve_knowledge_context
from app.knowledge.deposit import deposit_knowledge_draft
from app.pipelines.sample_pipeline import SampleAnalysisPipeline
from app.render.backend import RenderOptions
from app.render.hyperframes_backend import HyperFramesRenderBackend
from app.tools.hyperframes_tool import build_fixture_hyperframes_tool
from app.observability.sink import build_observability_sink
from app.runtime.checkpoint import (
    AnalysisCheckpoint,
    GenerationCheckpoint,
    analysis_artifact_root,
    generation_artifact_root,
    should_skip_analysis_stage,
    should_skip_generation_stage,
)
from app.runtime.task_context import TaskContext
from app.tools.llm_tool import LLMTool, LLMToolConfigError, LLMToolValidationError, default_fixture_llm
from app.validation.structure_validator import StructureValidationError


EmitFn = Callable[..., dict[str, Any]]
_AGENT_FAILURES = (
    LLMToolValidationError,
    LLMToolConfigError,
    StructureValidationError,
    KeyframeEncodingError,
    ValueError,
)


def _load_sample_analysis(
    storage_root: Path,
    project_id: str,
    sample_id: str,
    *,
    required: bool = True,
) -> dict[str, Any] | None:
    analysis_path = (
        storage_root
        / "projects"
        / project_id
        / "samples"
        / sample_id
        / "analysis"
        / "sample-analysis.json"
    )
    if not analysis_path.is_file():
        if required:
            raise FileNotFoundError(str(analysis_path))
        return None
    return json.loads(analysis_path.read_text(encoding="utf-8"))


def _generation_inputs_hash(user_brief: dict[str, Any], assets: list[dict[str, Any]]) -> str:
    payload = json.dumps({"brief": user_brief, "assets": assets}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class P0DemoPipeline:
    def __init__(
        self,
        storage_root: str | Path,
        llm: LLMTool | None = None,
        database_path: str | Path | None = None,
    ) -> None:
        self._storage_root = Path(storage_root)
        self._database_path = Path(database_path) if database_path is not None else None
        self._sample_pipeline = SampleAnalysisPipeline(self._storage_root)
        self._llm = llm if llm is not None else self._resolve_llm()

    def _resolve_llm(self) -> LLMTool:
        if is_fixture_mode():
            return default_fixture_llm()
        if self._database_path is None:
            raise LLMToolConfigError(
                "Live mode requires databasePath in worker payload (ModelGateway SQLite config)"
            )
        store = ModelGatewayStore(self._database_path, self._storage_root)
        gateway = ModelGateway.from_store(store)
        return LLMTool(fixture_mode=False, gateway=gateway)

    def _build_runner(self) -> AgentRunner:
        return AgentRunner(
            llm=self._llm,
            prompt_loader=PromptLoader(),
            observability_sink=build_observability_sink(self._storage_root),
            model_name="fixture" if self._llm.fixture_mode else "live",
        )

    def _build_material_gateway(self) -> ModelGateway | FixtureMaterialGateway:
        if self._llm.gateway is not None:
            return self._llm.gateway
        if self._llm.fixture_mode:
            return FixtureMaterialGateway()
        raise LLMToolConfigError("No ModelGateway configured for live mode")

    def _uses_fixture_runtime(self) -> bool:
        if self._llm.gateway is not None:
            return is_fixture_material_gateway(self._llm.gateway)
        return self._llm.fixture_mode

    def analyze_sample(
        self,
        *,
        project_id: str,
        task_id: str,
        sample_id: str,
        video_path: str | Path | None = None,
        source_url: str | None = None,
        cookies_path: str | Path | None = None,
        emit: EmitFn,
        resume: bool = False,
    ) -> dict[str, Any]:
        emit(
            status="running",
            stage="extracting_metadata",
            progress=5,
            message="Starting sample analysis" + (" (resume)" if resume else ""),
        )
        result = self._sample_pipeline.run(
            project_id,
            sample_id,
            task_id,
            video_path=video_path,
            source_url=source_url,
            cookies_path=cookies_path,
            resume=resume,
        )
        final_event = result.get("finalEvent", {})
        if final_event.get("status") == "failed":
            emit(
                status="failed",
                stage=str(final_event.get("stage", "extracting_metadata")),
                progress=int(final_event.get("progress", 0)),
                message=str(final_event.get("message", "sample analysis failed")),
                error=final_event.get("error"),
            )
            return {"ok": False, "finalEvent": final_event, "resumeSummary": result.get("resumeSummary")}

        project_root = self._storage_root / "projects" / project_id
        analysis_root = analysis_artifact_root(project_root, sample_id)
        checkpoint_path = analysis_root / "checkpoint.json"
        checkpoint = AnalysisCheckpoint.load(checkpoint_path)

        context = TaskContext(
            project_id=project_id,
            task_id=task_id,
            storage_root=self._storage_root,
        )
        runner = self._build_runner()

        sample_analysis = _load_sample_analysis(self._storage_root, project_id, sample_id)
        if should_skip_analysis_stage("extracting_visual_facts", checkpoint, analysis_root, resume=resume):
            emit(
                status="running",
                stage="extracting_visual_facts",
                progress=88,
                message="(resumed) visual facts already extracted",
            )
        else:
            emit(
                status="running",
                stage="extracting_visual_facts",
                progress=86,
                message="Extracting batched visual facts from keyframes",
            )
            warnings: list[str] = []
            try:
                result = run_visual_facts_extraction(
                    runner,
                    sample_analysis=sample_analysis,
                    analysis_root=analysis_root,
                    context=context,
                )
                if result.warnings:
                    warnings.extend(result.warnings)
                if not result.stage_complete:
                    emit(
                        status="failed",
                        stage="extracting_visual_facts",
                        progress=86,
                        message="Visual facts extraction incomplete",
                        error={
                            "code": "vision_batch_incomplete",
                            "message": "Batch vision did not reach minimum coverage; retry to resume missing batches",
                            "retryable": True,
                        },
                    )
                    return {"ok": False, "error": "visual facts incomplete", "finalEvent": {
                        "status": "failed",
                        "stage": "extracting_visual_facts",
                        "progress": 86,
                        "message": "Visual facts extraction incomplete",
                        "error": {
                            "code": "vision_batch_incomplete",
                            "message": "Batch vision did not reach minimum coverage",
                            "retryable": True,
                        },
                    }}
                sample_analysis = _load_sample_analysis(self._storage_root, project_id, sample_id)
                if warnings:
                    sample_analysis = merge_visual_facts_into_sample_analysis(
                        sample_analysis,
                        batch_digests=list(sample_analysis.get("keyframeBatchDigests") or []),
                        warnings=warnings,
                    )
                    persist_sample_analysis(analysis_root, sample_analysis)
            except _AGENT_FAILURES as exc:
                error = tool_error_from_agent_failure(exc)
                emit(
                    status="failed",
                    stage="extracting_visual_facts",
                    progress=86,
                    message="Visual facts extraction failed",
                    error=error,
                )
                return {"ok": False, "error": str(exc), "finalEvent": {
                    "status": "failed",
                    "stage": "extracting_visual_facts",
                    "progress": 86,
                    "message": "Visual facts extraction failed",
                    "error": error,
                }}
            checkpoint.mark_stage_complete("extracting_visual_facts")
            checkpoint.save(checkpoint_path)

        structure: dict[str, Any] | None = None
        if should_skip_analysis_stage("extracting_structure", checkpoint, analysis_root, resume=resume):
            structure_path = analysis_root / "video-structure.json"
            structure = json.loads(structure_path.read_text(encoding="utf-8"))
            emit(
                status="running",
                stage="extracting_structure",
                progress=92,
                message="(resumed) video structure already extracted",
            )
        else:
            emit(
                status="running",
                stage="extracting_structure",
                progress=92,
                message="Extracting video structure",
            )
            sample_analysis = _load_sample_analysis(self._storage_root, project_id, sample_id)
            try:
                structure = run_structure_analysis_pipeline(
                    runner,
                    analysis=sample_analysis,
                    context=context,
                    project_id=project_id,
                    source_video_id=sample_id,
                    analysis_root=analysis_root,
                    emit=emit,
                    checkpoint=checkpoint,
                    checkpoint_path=checkpoint_path,
                    resume=resume,
                )
            except _AGENT_FAILURES as exc:
                error = tool_error_from_agent_failure(exc)
                emit(
                    status="failed",
                    stage="extracting_structure",
                    progress=92,
                    message="Structure agent failed",
                    error=error,
                )
                return {"ok": False, "error": str(exc), "finalEvent": {
                    "status": "failed",
                    "stage": "extracting_structure",
                    "progress": 92,
                    "message": "Structure agent failed",
                    "error": error,
                }}
            structure_path = analysis_root / "video-structure.json"
            structure_path.parent.mkdir(parents=True, exist_ok=True)
            structure_path.write_text(
                json.dumps(structure, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            checkpoint.mark_stage_complete("extracting_structure")
            checkpoint.save(checkpoint_path)

        sample_analysis = _load_sample_analysis(self._storage_root, project_id, sample_id)

        knowledge_draft: dict[str, Any] | None = None
        if should_skip_analysis_stage("rendering_knowledge_draft", checkpoint, analysis_root, resume=resume):
            emit(
                status="running",
                stage="rendering_knowledge_draft",
                progress=96,
                message="(resumed) knowledge draft already rendered",
            )
        elif structure is not None:
            emit(
                status="running",
                stage="rendering_knowledge_draft",
                progress=96,
                message="Rendering knowledge skill draft",
            )
            try:
                knowledge_draft = deposit_knowledge_draft(
                    runner,
                    storage_root=self._storage_root,
                    project_id=project_id,
                    sample_id=sample_id,
                    structure=structure,
                    sample_analysis=sample_analysis,
                    context=context,
                )
                checkpoint.mark_stage_complete("rendering_knowledge_draft")
                checkpoint.save(checkpoint_path)
            except Exception as exc:
                emit(
                    status="running",
                    stage="rendering_knowledge_draft",
                    progress=96,
                    message=f"Knowledge draft skipped: {exc}",
                )

        emit(
            status="succeeded",
            stage="completed",
            progress=100,
            message="Sample analysis and structure extraction completed",
            artifact_refs=result.get("artifactRefs"),
        )
        return {
            "ok": True,
            "structure": structure,
            "sampleAnalysis": sample_analysis,
            "knowledgeDraft": knowledge_draft,
            "resumeSummary": result.get("resumeSummary"),
        }

    def run_generation(
        self,
        *,
        project_id: str,
        task_id: str,
        generation_id: str,
        structure: dict[str, Any],
        user_brief: dict[str, Any],
        assets: list[dict[str, Any]],
        emit: EmitFn,
        resume: bool = False,
        variant: str = "default",
        sample_selection: dict[str, Any] | None = None,
        generation_run_id: str | None = None,
    ) -> dict[str, Any]:
        project_root = self._storage_root / "projects" / project_id
        generation_root = generation_artifact_root(project_root, generation_id)
        generation_root.mkdir(parents=True, exist_ok=True)
        render_root = project_root / "renders" / generation_id

        checkpoint_path = generation_root / "checkpoint.json"
        checkpoint = GenerationCheckpoint.load(checkpoint_path)
        if not checkpoint.generationId:
            checkpoint.generationId = generation_id

        inputs_hash = _generation_inputs_hash(user_brief, assets)
        if resume and checkpoint.inputsHash and checkpoint.inputsHash != inputs_hash:
            checkpoint = GenerationCheckpoint(generationId=generation_id, inputsHash=inputs_hash)
            checkpoint.save(checkpoint_path)
            resume = False
        elif not checkpoint.inputsHash:
            checkpoint.inputsHash = inputs_hash

        context = TaskContext(
            project_id=project_id,
            task_id=task_id,
            storage_root=self._storage_root,
        )
        runner = self._build_runner()
        revise_context = load_revise_context(generation_root) if resume else None

        sample_analysis_for_gen = (
            _load_sample_analysis(
                self._storage_root,
                project_id,
                str(structure.get("sourceVideoId") or ""),
                required=False,
            )
            if structure.get("sourceVideoId")
            else None
        )
        knowledge_context = resolve_knowledge_context(
            storage_root=self._storage_root,
            database_path=self._database_path,
            project_id=project_id,
            level=1,
            video_structure=structure,
            sample_analysis=sample_analysis_for_gen,
        )

        reference_structures: list[dict[str, Any]] = []
        primary_sample_id = str(structure.get("sourceVideoId") or "")
        if sample_selection:
            refs = sample_selection.get("referenceStructures")
            if isinstance(refs, list):
                reference_structures = [item for item in refs if isinstance(item, dict)]
            primary_sample_id = str(
                sample_selection.get("primarySampleId") or primary_sample_id
            )

        if reference_structures and generation_run_id:
            from app.agents.structure_synthesizer import run_structure_synthesizer

            emit(
                status="running",
                stage="synthesizing_structure",
                progress=6,
                message="Synthesizing structure from multiple sample references",
            )
            synthesized, provenance = run_structure_synthesizer(
                runner,
                context=context,
                project_id=project_id,
                generation_run_id=str(generation_run_id),
                primary_sample_id=primary_sample_id,
                primary_structure=structure,
                reference_structures=reference_structures,
                reference_sample_ids=[
                    str(item)
                    for item in (sample_selection or {}).get("referenceSampleIds") or []
                ],
                user_brief=user_brief,
                knowledge_context=knowledge_context,
            )
            structure = synthesized
            (generation_root / "synthesized-structure.json").write_text(
                json.dumps(structure, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            (generation_root / "structure-provenance.json").write_text(
                json.dumps(provenance, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

        inventory: dict[str, Any] | None = None
        gap_report: dict[str, Any] | None = None
        plan: dict[str, Any] | None = None
        slot_matches: list[dict[str, Any]] = []

        if should_skip_generation_stage("analyzing_assets", checkpoint, generation_root, resume=resume):
            inventory = json.loads((generation_root / "asset-inventory.json").read_text(encoding="utf-8"))
            emit(
                status="running",
                stage="analyzing_assets",
                progress=10,
                message="(resumed) asset inventory ready",
            )
        else:
            emit(
                status="running",
                stage="analyzing_assets",
                progress=10,
                message="Analyzing user brief and uploaded assets",
            )
            try:
                inventory_baseline = build_asset_inventory(
                    project_id=project_id,
                    user_brief=user_brief,
                    assets=assets,
                )
                inventory = run_asset_understanding(
                    runner,
                    inventory=inventory_baseline,
                    context=context,
                    generation_id=generation_id,
                )
            except _AGENT_FAILURES as exc:
                emit(
                    status="failed",
                    stage="analyzing_assets",
                    progress=10,
                    message="Asset understanding failed",
                    error={"code": "agent_failed", "message": str(exc)},
                )
                return {"ok": False, "error": str(exc)}

            checkpoint.mark_stage_complete("analyzing_assets")
            checkpoint.save(checkpoint_path)

        if should_skip_generation_stage("planning_completion", checkpoint, generation_root, resume=resume):
            gap_report = json.loads((generation_root / "gap-report.json").read_text(encoding="utf-8"))
            plan = json.loads((generation_root / "generation-plan.json").read_text(encoding="utf-8"))
            emit(
                status="running",
                stage="mapping_slots",
                progress=35,
                message="(resumed) slot mapping ready",
            )
            emit(
                status="running",
                stage="planning_completion",
                progress=55,
                message="(resumed) generation plan ready",
            )
        elif should_skip_generation_stage("mapping_slots", checkpoint, generation_root, resume=resume):
            gap_report = json.loads((generation_root / "gap-report.json").read_text(encoding="utf-8"))
            slot_matches_payload = json.loads((generation_root / "slot-matches.json").read_text(encoding="utf-8"))
            slot_matches = list(slot_matches_payload.get("slotMatches", []))
            emit(
                status="running",
                stage="mapping_slots",
                progress=35,
                message="(resumed) slot mapping ready",
            )
            emit(
                status="running",
                stage="planning_completion",
                progress=55,
                message="Revising storyboard and packaging",
            )
            try:
                inventory, slot_matches, gap_report, plan = run_planning_completion(
                    runner,
                    structure=structure,
                    inventory=inventory,
                    slot_matches=slot_matches,
                    gap_report=gap_report,
                    context=context,
                    generation_id=generation_id,
                    variant=variant,
                    revise_context=revise_context,
                    generation_root=generation_root,
                    knowledge_context=knowledge_context,
                )
            except _AGENT_FAILURES as exc:
                emit(
                    status="failed",
                    stage="planning_completion",
                    progress=55,
                    message="Planning completion failed",
                    error={"code": "agent_failed", "message": str(exc)},
                )
                return {"ok": False, "error": str(exc)}

            plan["id"] = generation_id
            (generation_root / "generation-plan.json").write_text(
                json.dumps(plan, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            checkpoint.mark_stage_complete("planning_completion")
            checkpoint.save(checkpoint_path)
        else:
            emit(
                status="running",
                stage="mapping_slots",
                progress=35,
                message="Mapping structure slots to assets",
            )
            try:
                inventory, mapping_slot_matches, gap_report, plan = run_agent_generation(
                    runner,
                    structure=structure,
                    inventory=inventory,
                    context=context,
                    generation_id=generation_id,
                    variant=variant,
                    revise_context=revise_context,
                    knowledge_context=knowledge_context,
                    database_path=self._database_path,
                    sample_analysis=sample_analysis_for_gen,
                )
                slot_matches = mapping_slot_matches
            except _AGENT_FAILURES as exc:
                emit(
                    status="failed",
                    stage="mapping_slots",
                    progress=35,
                    message="Generation agent failed",
                    error={"code": "agent_failed", "message": str(exc)},
                )
                return {"ok": False, "error": str(exc)}

            plan["id"] = generation_id
            (generation_root / "asset-inventory.json").write_text(
                json.dumps(inventory, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            (generation_root / "slot-matches.json").write_text(
                json.dumps({"slotMatches": mapping_slot_matches}, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            (generation_root / "gap-report.json").write_text(
                json.dumps(gap_report, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            (generation_root / "generation-plan.json").write_text(
                json.dumps(plan, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            checkpoint.mark_stage_complete("mapping_slots")
            checkpoint.mark_stage_complete("planning_completion")
            checkpoint.save(checkpoint_path)
            emit(
                status="running",
                stage="planning_completion",
                progress=55,
                message="Planning completion actions",
            )

        slot_matches_path = generation_root / "slot-matches.json"
        if slot_matches_path.is_file():
            slot_matches_payload = json.loads(slot_matches_path.read_text(encoding="utf-8"))
            slot_matches = list(slot_matches_payload.get("slotMatches", []))

        material_state_path = generation_root / "material-state.json"
        material_skipped = resume and is_material_stage_done(generation_root, plan)
        if material_skipped:
            emit(
                status="running",
                stage="generating_material",
                progress=62,
                message="(resumed) generated materials ready",
                artifact_refs=context.artifact_refs,
            )
        else:
            emit(
                status="running",
                stage="generating_material",
                progress=60,
                message="Generating AIGC completion materials",
                artifact_refs=context.artifact_refs,
            )

            def material_progress(stage: str, message: str) -> None:
                emit(
                    status="running",
                    stage=stage,
                    progress=65,
                    message=message,
                    artifact_refs=list(context.artifact_refs),
                )

            try:
                gap_report_path = generation_root / "gap-report.json"
                material_gap_report = None
                if gap_report_path.is_file():
                    material_gap_report = json.loads(
                        gap_report_path.read_text(encoding="utf-8"),
                    )
                plan, _material_results = run_generating_material(
                    plan=plan,
                    inventory=inventory,
                    slot_matches=slot_matches,
                    structure=structure,
                    generation_root=generation_root,
                    render_root=render_root,
                    gateway=self._build_material_gateway(),
                    emit_progress=material_progress,
                    register_artifact=context.register_artifact,
                    material_state_path=material_state_path,
                    gap_report=material_gap_report,
                    runner=runner,
                    task_context=context,
                    variant_overrides=load_variant_gap_planner_overrides(str(plan.get("variant", variant))),
                )
            except ToolError as exc:
                checkpoint.mark_failed("generating_material")
                checkpoint.save(checkpoint_path)
                emit(
                    status="failed",
                    stage="generating_material",
                    progress=60,
                    message="Material generation failed",
                    error={
                        "code": exc.code,
                        "message": exc.message,
                        "retryable": exc.retryable,
                    },
                )
                return {"ok": False, "error": str(exc)}

            (generation_root / "generation-plan.json").write_text(
                json.dumps(plan, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            checkpoint.mark_stage_complete("generating_material")
            checkpoint.save(checkpoint_path)
            emit(
                status="running",
                stage="generating_material",
                progress=70,
                message="AIGC materials generated",
                artifact_refs=list(context.artifact_refs),
            )

        if should_skip_generation_stage("building_timeline", checkpoint, generation_root, resume=resume):
            emit(
                status="running",
                stage="building_timeline",
                progress=75,
                message="(resumed) timeline ready",
            )
        else:
            emit(
                status="running",
                stage="building_timeline",
                progress=75,
                message="Building HyperFrames composition",
            )
            checkpoint.mark_stage_complete("building_timeline")
            checkpoint.save(checkpoint_path)

        render_output = None
        if should_skip_generation_stage(
            "rendering",
            checkpoint,
            generation_root,
            resume=resume,
            render_root=render_root,
        ):
            emit(
                status="running",
                stage="rendering",
                progress=90,
                message="(resumed) render preview already available",
            )
            checkpoint.mark_stage_complete("rendering")
            checkpoint.save(checkpoint_path)
        else:

            def render_progress(stage: str) -> None:
                stage_map = {
                    "building_timeline": (80, "Building HyperFrames composition"),
                    "rendering": (90, "Rendering preview"),
                    "completed": (98, "Finalizing render output"),
                }
                progress, message = stage_map.get(stage, (85, "Rendering"))
                emit(
                    status="running",
                    stage="rendering" if stage != "building_timeline" else "building_timeline",
                    progress=progress,
                    message=message,
                )

            render_tool = build_fixture_hyperframes_tool() if self._uses_fixture_runtime() else None
            backend = HyperFramesRenderBackend(tool=render_tool)
            render_output = backend.render(
                RenderOptions(
                    project_id=project_id,
                    generation_id=generation_id,
                    timeline=plan["timeline"],
                    storage_root=self._storage_root,
                    emit_progress=render_progress,
                )
            )

            if render_output.error and not render_output.artifact_refs:
                checkpoint.mark_failed("rendering")
                checkpoint.save(checkpoint_path)
                emit(
                    status="failed",
                    stage="rendering",
                    progress=90,
                    message="Render failed",
                    error=render_output.error,
                )
                return {
                    "ok": False,
                    "inventory": inventory,
                    "gapReport": gap_report,
                    "plan": plan,
                }

            checkpoint.mark_stage_complete("rendering")
            checkpoint.save(checkpoint_path)

        artifact_refs = render_output.artifact_refs if render_output is not None else []
        emit(
            status="succeeded",
            stage="completed",
            progress=100,
            message="Generation plan and preview ready",
            artifact_refs=artifact_refs,
        )
        return {
            "ok": True,
            "inventory": inventory,
            "gapReport": gap_report,
            "plan": plan,
            "renderArtifacts": artifact_refs,
        }

    def run_revise(
        self,
        *,
        project_id: str,
        task_id: str,
        source_generation_id: str,
        generation_id: str,
        instruction: str,
        structure: dict[str, Any],
        user_brief: dict[str, Any],
        assets: list[dict[str, Any]],
        emit: EmitFn,
        intents: list[dict[str, Any]] | None = None,
        variant: str | None = None,
        resume: bool = False,
    ) -> dict[str, Any]:
        project_root = self._storage_root / "projects" / project_id
        target_root = generation_artifact_root(project_root, generation_id)
        generation_root = target_root

        if resume:
            revise_context = load_revise_context(generation_root)
            if revise_context is None:
                emit(
                    status="failed",
                    stage="parsing_edit_intent",
                    progress=0,
                    message="Revise context not found for resume",
                    error={"code": "revise_context_missing", "message": "revise-context.json missing"},
                )
                return {"ok": False, "error": "revise-context.json missing"}
            edit_intent_path = generation_root / "edit-intent.json"
            if not edit_intent_path.is_file():
                emit(
                    status="failed",
                    stage="parsing_edit_intent",
                    progress=0,
                    message="Edit intents not found for resume",
                    error={"code": "edit_intent_missing", "message": "edit-intent.json missing"},
                )
                return {"ok": False, "error": "edit-intent.json missing"}
            parsed_intents = json.loads(edit_intent_path.read_text(encoding="utf-8")).get("intents", [])
            source_generation_id = str(
                json.loads((generation_root / "revise-context.json").read_text(encoding="utf-8")).get(
                    "sourceGenerationId",
                    source_generation_id,
                )
            )
            plan_path = generation_artifact_root(project_root, source_generation_id) / "generation-plan.json"
            source_plan = json.loads(plan_path.read_text(encoding="utf-8")) if plan_path.is_file() else {}
            resolved_variant = variant or str(source_plan.get("variant", "default"))
        else:
            source_root = generation_artifact_root(project_root, source_generation_id)
            plan_path = source_root / "generation-plan.json"
            if not plan_path.is_file():
                emit(
                    status="failed",
                    stage="parsing_edit_intent",
                    progress=0,
                    message="Source generation plan not found",
                    error={"code": "source_not_found", "message": "generation-plan.json missing"},
                )
                return {"ok": False, "error": "source generation-plan.json missing"}

            source_plan = json.loads(plan_path.read_text(encoding="utf-8"))
            resolved_variant = variant or str(source_plan.get("variant", "default"))

            context = TaskContext(
                project_id=project_id,
                task_id=task_id,
                storage_root=self._storage_root,
            )
            runner = self._build_runner()

            emit(
                status="running",
                stage="parsing_edit_intent",
                progress=5,
                message="Parsing natural language edit instruction",
            )
            try:
                parsed_intents = parse_instruction_intents(
                    runner,
                    instruction=instruction,
                    source_plan=source_plan,
                    context=context,
                    generation_id=generation_id,
                    pre_parsed_intents=intents,
                )
            except _AGENT_FAILURES as exc:
                emit(
                    status="failed",
                    stage="parsing_edit_intent",
                    progress=5,
                    message="Edit intent parsing failed",
                    error={"code": "agent_failed", "message": str(exc)},
                )
                return {"ok": False, "error": str(exc)}

            source_timeline = source_plan.get("timeline") if isinstance(source_plan.get("timeline"), dict) else {}
            revise_context = apply_intents_to_context(
                parsed_intents,
                source_plan=source_plan,
                source_timeline=source_timeline,
            )

            emit(
                status="running",
                stage="applying_edit_intent",
                progress=12,
                message="Applying edit intents and forking generation",
            )
            seed_revise_generation(
                project_root=project_root,
                source_generation_id=source_generation_id,
                target_generation_id=generation_id,
                intents=parsed_intents,
                revise_context=revise_context,
                instruction=instruction,
            )

        result = self.run_generation(
            project_id=project_id,
            task_id=task_id,
            generation_id=generation_id,
            structure=structure,
            user_brief=user_brief,
            assets=assets,
            emit=emit,
            resume=True,
            variant=resolved_variant,
        )
        if result.get("ok"):
            result["intents"] = parsed_intents
            result["sourceGenerationId"] = source_generation_id
        return result
