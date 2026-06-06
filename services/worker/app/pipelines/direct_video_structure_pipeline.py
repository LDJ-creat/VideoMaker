from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from app.agents.runner import AgentRunner
from app.agents.video_structure_analyst import run_video_structure_analyst
from app.perception.sample_facts import persist_sample_analysis
from app.pipelines.sample_analysis_progress import (
    DIRECT_STRUCTURE_PROGRESS_SAVED,
    DIRECT_STRUCTURE_PROGRESS_START,
    DIRECT_STRUCTURE_PROGRESS_VALIDATE,
)
from app.runtime.checkpoint import AnalysisCheckpoint
from app.runtime.task_context import TaskContext
from app.validation.structure_quality import evaluate_structure_quality


EmitFn = Callable[..., None]
_ROUTE_WARNING = "analysis_route:direct_multimodal"


def resolve_sample_video_path(
    analysis_root: Path,
    checkpoint: AnalysisCheckpoint,
) -> Path:
    if checkpoint.videoPath:
        candidate = Path(checkpoint.videoPath)
        if candidate.is_file():
            return candidate
    for name in ("source.mp4", "original.mp4"):
        candidate = analysis_root.parent / name
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        f"No sample video found under {analysis_root.parent} for direct multimodal analysis"
    )


def run_direct_video_structure_pipeline(
    runner: AgentRunner,
    *,
    analysis: dict[str, Any],
    video_path: Path,
    analysis_root: Path,
    context: TaskContext,
    project_id: str,
    source_video_id: str,
    checkpoint: AnalysisCheckpoint,
    checkpoint_path: Path,
    emit: EmitFn | None = None,
) -> dict[str, Any]:
    if emit is not None:
        emit(
            status="running",
            stage="extracting_structure_direct",
            progress=DIRECT_STRUCTURE_PROGRESS_START,
            message="Direct multimodal structure extraction",
        )

    structure = run_video_structure_analyst(
        runner,
        analysis=analysis,
        video_path=video_path,
        context=context,
        project_id=project_id,
        source_video_id=source_video_id,
        analysis_root=analysis_root,
        progress=DIRECT_STRUCTURE_PROGRESS_START + 3,
    )

    if emit is not None:
        emit(
            status="running",
            stage="extracting_structure_direct",
            progress=DIRECT_STRUCTURE_PROGRESS_VALIDATE,
            message="Validating direct multimodal structure output",
        )

    quality = evaluate_structure_quality(structure)
    analysis_quality = dict(structure.get("analysisQuality") or {})
    analysis_quality["locale"] = str(analysis.get("locale") or analysis_quality.get("locale") or "zh")
    warnings = list(analysis_quality.get("warnings") or [])
    for warning in [_ROUTE_WARNING, *list(quality.get("warnings") or [])]:
        if warning not in warnings:
            warnings.append(warning)
    analysis_quality["warnings"] = warnings
    analysis_quality["promoteReady"] = bool(quality.get("promoteReady"))
    structure["analysisQuality"] = analysis_quality
    structure.setdefault("projectId", project_id)
    structure.setdefault("sourceVideoId", source_video_id)
    structure.setdefault("version", "p1-v3")

    structure_path = analysis_root / "video-structure.json"
    structure_path.parent.mkdir(parents=True, exist_ok=True)
    structure_path.write_text(json.dumps(structure, indent=2, ensure_ascii=False), encoding="utf-8")

    merged_analysis = dict(analysis)
    merged_analysis["structureAnalysisRoute"] = "direct_multimodal"
    persist_sample_analysis(analysis_root, merged_analysis)

    checkpoint.analysisRoute = "direct_multimodal"
    checkpoint.mark_stage_complete("extracting_structure_direct")
    checkpoint.save(checkpoint_path)

    if emit is not None:
        emit(
            status="running",
            stage="extracting_structure_direct",
            progress=DIRECT_STRUCTURE_PROGRESS_SAVED,
            message="Direct multimodal structure saved",
        )

    return structure
