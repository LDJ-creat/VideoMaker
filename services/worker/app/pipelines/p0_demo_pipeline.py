from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from app.agents.prompt_loader import PromptLoader
from app.agents.runner import AgentRunner
from app.agents.structure_inputs import KeyframeEncodingError
from app.agents.structure_analyst import run_structure_analyst
from app.config.variants import load_variant_gap_planner_overrides
from app.gateway.model_gateway import ModelGateway
from app.pipelines.generation_pipeline import (
    FixtureMaterialGateway,
    build_asset_inventory,
    is_material_stage_done,
    run_agent_generation,
    run_generating_material,
)
from app.tools.image_gen_tool import ToolError
from app.pipelines.asset_understanding import run_asset_understanding
from app.pipelines.sample_pipeline import SampleAnalysisPipeline
from app.render.backend import RenderOptions
from app.render.hyperframes_backend import HyperFramesRenderBackend
from app.runtime.agent_run_store import AgentRunStore
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


def _load_sample_analysis(storage_root: Path, project_id: str, sample_id: str) -> dict[str, Any]:
    analysis_path = (
        storage_root
        / "projects"
        / project_id
        / "samples"
        / sample_id
        / "analysis"
        / "sample-analysis.json"
    )
    return json.loads(analysis_path.read_text(encoding="utf-8"))


def _generation_inputs_hash(user_brief: dict[str, Any], assets: list[dict[str, Any]]) -> str:
    payload = json.dumps({"brief": user_brief, "assets": assets}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class P0DemoPipeline:
    def __init__(
        self,
        storage_root: str | Path,
        llm: LLMTool | None = None,
    ) -> None:
        self._storage_root = Path(storage_root)
        self._sample_pipeline = SampleAnalysisPipeline(self._storage_root)
        self._llm = llm or default_fixture_llm()

    def _build_runner(self) -> AgentRunner:
        return AgentRunner(
            llm=self._llm,
            prompt_loader=PromptLoader(),
            run_store=AgentRunStore(self._storage_root),
            model_name="fixture" if self._llm.fixture_mode else "live",
        )

    def _build_material_gateway(self) -> ModelGateway | FixtureMaterialGateway:
        if self._llm.gateway is not None:
            return self._llm.gateway
        if self._llm.fixture_mode:
            return FixtureMaterialGateway()
        return ModelGateway.from_env()

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
                structure = run_structure_analyst(
                    runner,
                    analysis=sample_analysis,
                    context=context,
                    project_id=project_id,
                    source_video_id=sample_id,
                    analysis_root=analysis_root,
                )
            except _AGENT_FAILURES as exc:
                emit(
                    status="failed",
                    stage="extracting_structure",
                    progress=92,
                    message="Structure agent failed",
                    error={"code": "agent_failed", "message": str(exc)},
                )
                return {"ok": False, "error": str(exc)}
            structure_path = analysis_root / "video-structure.json"
            structure_path.parent.mkdir(parents=True, exist_ok=True)
            structure_path.write_text(
                json.dumps(structure, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            checkpoint.mark_stage_complete("extracting_structure")
            checkpoint.save(checkpoint_path)

        sample_analysis = _load_sample_analysis(self._storage_root, project_id, sample_id)
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

        inventory: dict[str, Any] | None = None
        gap_report: dict[str, Any] | None = None
        plan: dict[str, Any] | None = None
        slot_matches: list[dict[str, Any]] = []

        if should_skip_generation_stage("planning_completion", checkpoint, generation_root, resume=resume):
            inventory = json.loads((generation_root / "asset-inventory.json").read_text(encoding="utf-8"))
            gap_report = json.loads((generation_root / "gap-report.json").read_text(encoding="utf-8"))
            plan = json.loads((generation_root / "generation-plan.json").read_text(encoding="utf-8"))
            emit(
                status="running",
                stage="analyzing_assets",
                progress=10,
                message="(resumed) asset inventory ready",
            )
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
                )
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
                    runner=runner,
                    task_context=context,
                    variant_overrides=load_variant_gap_planner_overrides(str(plan.get("variant", "default"))),
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

            backend = HyperFramesRenderBackend()
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
