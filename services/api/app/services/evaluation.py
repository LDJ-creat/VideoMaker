from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from evaluation.artifacts import find_generation_mp4, read_json, target_duration_sec
from evaluation.final_video_qa import run_final_video_qa
from evaluation.report_builder import build_evaluation_report, write_evaluation_report
from knowledge.paths import validate_storage_segment


def _lazy_build_enabled() -> bool:
    return os.getenv("VIDEOMAKER_EVAL_LAZY_BUILD", "true").strip().lower() != "false"


def _generation_report_path(generation_root: Path, *, partial: bool = False) -> Path:
    name = "evaluation-report.partial.json" if partial else "evaluation-report.json"
    return generation_root / name


def _technical_qa_for_generation(generation_root: Path, *, partial: bool) -> dict[str, Any] | None:
    if partial:
        return None
    mp4_path = find_generation_mp4(generation_root)
    if mp4_path is None:
        return None
    return run_final_video_qa(
        mp4_path,
        target_duration_sec=target_duration_sec(generation_root),
    )


def _validated_generation_root(storage_root: Path, project_id: str, generation_id: str) -> Path:
    validate_storage_segment(project_id, field="project_id")
    validate_storage_segment(generation_id, field="generation_id")
    return storage_root / "projects" / project_id / "generations" / generation_id


def get_or_build_generation_evaluation(
    storage_root: Path,
    *,
    project_id: str,
    generation_id: str,
    task_id: str | None,
    variant_id: str | None,
    task_events: list[dict[str, Any]] | None,
    rebuild: bool = False,
) -> dict[str, Any]:
    generation_root = _validated_generation_root(storage_root, project_id, generation_id)
    report_path = _generation_report_path(generation_root)
    if not rebuild and report_path.is_file():
        cached = read_json(report_path)
        if cached:
            return cached

    if not rebuild and not _lazy_build_enabled():
        raise FileNotFoundError("evaluation_report_missing")

    technical_qa = _technical_qa_for_generation(generation_root, partial=False)
    report = build_evaluation_report(
        storage_root,
        project_id=project_id,
        generation_id=generation_id,
        task_id=task_id,
        variant_id=variant_id,
        partial=False,
        task_events=task_events,
        technical_qa=technical_qa,
    )
    write_evaluation_report(storage_root, report, partial=False)
    return report


def build_run_evaluation_summary(
    storage_root: Path,
    *,
    project_id: str,
    run_id: str,
    generation_ids: list[str],
    task_events_by_generation: dict[str, list[dict[str, Any]]] | None = None,
    rebuild: bool = False,
) -> dict[str, Any]:
    validate_storage_segment(project_id, field="project_id")
    validate_storage_segment(run_id, field="run_id")

    variants: list[dict[str, Any]] = []
    for generation_id in generation_ids:
        task_events = (task_events_by_generation or {}).get(generation_id)
        try:
            report = get_or_build_generation_evaluation(
                storage_root,
                project_id=project_id,
                generation_id=generation_id,
                task_id=None,
                variant_id=None,
                task_events=task_events,
                rebuild=rebuild,
            )
        except FileNotFoundError:
            continue
        variants.append(
            {
                "generationId": generation_id,
                "verdict": report.get("verdict"),
                "scores": report.get("scores"),
                "observability": report.get("observability"),
            }
        )

    summary = {
        "version": "1.0",
        "runId": run_id,
        "projectId": project_id,
        "variants": variants,
    }
    run_dir = storage_root / "projects" / project_id / "generation-runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "evaluation-summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return summary


def load_run_evaluation_summary(
    storage_root: Path,
    *,
    project_id: str,
    run_id: str,
) -> dict[str, Any] | None:
    validate_storage_segment(project_id, field="project_id")
    validate_storage_segment(run_id, field="run_id")
    path = storage_root / "projects" / project_id / "generation-runs" / run_id / "evaluation-summary.json"
    return read_json(path)
