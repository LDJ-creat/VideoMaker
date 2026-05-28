from __future__ import annotations

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


EmitFn = Callable[..., dict[str, Any]]


def _load_sample_analysis(storage_root: Path, project_id: str, task_id: str) -> dict[str, Any]:
    analysis_path = (
        storage_root
        / "projects"
        / project_id
        / "samples"
        / task_id
        / "sample-analysis.json"
    )
    return json.loads(analysis_path.read_text(encoding="utf-8"))


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
        emit: EmitFn,
    ) -> dict[str, Any]:
        emit(
            status="running",
            stage="extracting_metadata",
            progress=5,
            message="Starting sample analysis",
        )
        result = self._sample_pipeline.run(
            project_id,
            task_id,
            video_path=video_path,
            source_url=source_url,
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
            return {"ok": False, "finalEvent": final_event}

        emit(
            status="running",
            stage="extracting_structure",
            progress=92,
            message="Extracting video structure",
        )
        sample_analysis = _load_sample_analysis(self._storage_root, project_id, task_id)
        structure = extract_video_structure(
            sample_analysis=sample_analysis,
            project_id=project_id,
            source_video_id=sample_id,
        )
        structure_path = (
            self._storage_root
            / "projects"
            / project_id
            / "samples"
            / task_id
            / "video-structure.json"
        )
        structure_path.parent.mkdir(parents=True, exist_ok=True)
        structure_path.write_text(
            json.dumps(structure, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        emit(
            status="succeeded",
            stage="completed",
            progress=100,
            message="Sample analysis and structure extraction completed",
            artifact_refs=result.get("artifactRefs"),
        )
        return {"ok": True, "structure": structure, "sampleAnalysis": sample_analysis}

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
    ) -> dict[str, Any]:
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

        emit(
            status="running",
            stage="mapping_slots",
            progress=35,
            message="Mapping structure slots to assets",
        )
        mapping = map_slots(structure=structure, inventory=inventory)
        gap_report = build_gap_report(
            structure=structure,
            inventory=inventory,
            slot_matches=mapping.slot_matches,
        )

        emit(
            status="running",
            stage="planning_completion",
            progress=55,
            message="Planning completion actions",
        )
        plan = build_generation_plan(
            structure=structure,
            inventory=inventory,
            gap_report=gap_report,
            slot_matches=mapping.slot_matches,
        )
        plan["id"] = generation_id

        emit(
            status="running",
            stage="building_timeline",
            progress=75,
            message="Building HyperFrames composition",
        )

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

        emit(
            status="succeeded",
            stage="completed",
            progress=100,
            message="Generation plan and preview ready",
            artifact_refs=render_output.artifact_refs,
        )
        return {
            "ok": True,
            "inventory": inventory,
            "gapReport": gap_report,
            "plan": plan,
            "renderArtifacts": render_output.artifact_refs,
        }
