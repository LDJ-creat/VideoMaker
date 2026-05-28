from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from app.pipelines.generation_pipeline import (
    build_asset_inventory,
    build_gap_report,
    build_generation_plan,
    map_slots,
)
from app.pipelines.sample_pipeline import SampleAnalysisPipeline
from app.pipelines.structure_pipeline import extract_video_structure
from app.render.backend import RenderOptions
from app.render.hyperframes_backend import HyperFramesRenderBackend
from app.runtime.checkpoint import (
    AnalysisCheckpoint,
    GenerationCheckpoint,
    analysis_artifact_root,
    generation_artifact_root,
    should_skip_analysis_stage,
    should_skip_generation_stage,
)


EmitFn = Callable[..., dict[str, Any]]


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
    def __init__(self, storage_root: str | Path) -> None:
        self._storage_root = Path(storage_root)
        self._sample_pipeline = SampleAnalysisPipeline(self._storage_root)

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
            structure = extract_video_structure(
                sample_analysis=sample_analysis,
                project_id=project_id,
                source_video_id=sample_id,
            )
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

        inventory: dict[str, Any] | None = None
        gap_report: dict[str, Any] | None = None
        plan: dict[str, Any] | None = None
        mapping_slot_matches: list[dict[str, Any]] | None = None

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
                message="Building asset inventory",
            )
            inventory = build_asset_inventory(
                project_id=project_id,
                user_brief=user_brief,
                assets=assets,
            )
            (generation_root / "asset-inventory.json").write_text(
                json.dumps(inventory, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            checkpoint.mark_stage_complete("analyzing_assets")
            checkpoint.save(checkpoint_path)

        if should_skip_generation_stage("mapping_slots", checkpoint, generation_root, resume=resume):
            slot_data = json.loads((generation_root / "slot-matches.json").read_text(encoding="utf-8"))
            mapping_slot_matches = slot_data["slotMatches"]
            emit(
                status="running",
                stage="mapping_slots",
                progress=35,
                message="(resumed) slot mapping ready",
            )
        else:
            emit(
                status="running",
                stage="mapping_slots",
                progress=35,
                message="Mapping structure slots to assets",
            )
            mapping = map_slots(structure=structure, inventory=inventory)
            mapping_slot_matches = mapping.slot_matches
            (generation_root / "slot-matches.json").write_text(
                json.dumps({"slotMatches": mapping_slot_matches}, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            checkpoint.mark_stage_complete("mapping_slots")
            checkpoint.save(checkpoint_path)

        if should_skip_generation_stage("planning_completion", checkpoint, generation_root, resume=resume):
            gap_report = json.loads((generation_root / "gap-report.json").read_text(encoding="utf-8"))
            plan = json.loads((generation_root / "generation-plan.json").read_text(encoding="utf-8"))
            emit(
                status="running",
                stage="planning_completion",
                progress=55,
                message="(resumed) generation plan ready",
            )
        else:
            emit(
                status="running",
                stage="planning_completion",
                progress=55,
                message="Planning completion actions",
            )
            gap_report = build_gap_report(
                structure=structure,
                inventory=inventory,
                slot_matches=mapping_slot_matches,
            )
            plan = build_generation_plan(
                structure=structure,
                inventory=inventory,
                gap_report=gap_report,
                slot_matches=mapping_slot_matches,
            )
            plan["id"] = generation_id
            (generation_root / "gap-report.json").write_text(
                json.dumps(gap_report, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            (generation_root / "generation-plan.json").write_text(
                json.dumps(plan, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            checkpoint.mark_stage_complete("planning_completion")
            checkpoint.mark_stage_complete("building_timeline")
            checkpoint.save(checkpoint_path)

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
