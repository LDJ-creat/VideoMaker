from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from evaluation.artifacts import find_generation_mp4, target_duration_sec
from evaluation.eval_logging import log_evaluation_failure
from evaluation.final_video_qa import run_final_video_qa
from evaluation.report_builder import build_evaluation_report, write_evaluation_report


def _eval_enabled() -> bool:
    return os.getenv("VIDEOMAKER_EVAL_ENABLED", "true").strip().lower() != "false"


def _partial_on_gate() -> bool:
    return os.getenv("VIDEOMAKER_EVAL_PARTIAL_ON_GATE", "true").strip().lower() != "false"


def maybe_write_generation_evaluation(
    storage_root: Path,
    *,
    project_id: str,
    generation_id: str,
    task_id: str | None = None,
    variant_id: str | None = None,
    partial: bool = False,
) -> Path | None:
    if not _eval_enabled():
        return None
    if partial and not _partial_on_gate():
        return None

    try:
        generation_root = storage_root / "projects" / project_id / "generations" / generation_id
        technical_qa: dict[str, Any] | None = None
        if not partial:
            mp4_path = find_generation_mp4(generation_root)
            if mp4_path is not None:
                technical_qa = run_final_video_qa(
                    mp4_path,
                    target_duration_sec=target_duration_sec(generation_root),
                )

        report = build_evaluation_report(
            storage_root,
            project_id=project_id,
            generation_id=generation_id,
            task_id=task_id,
            variant_id=variant_id,
            partial=partial,
            technical_qa=technical_qa,
        )
        return write_evaluation_report(storage_root, report, partial=partial)
    except Exception as exc:
        log_evaluation_failure(
            "generation",
            project_id=project_id,
            entity_id=generation_id,
            exc=exc,
        )
        return None


def maybe_write_sample_analysis_evaluation(
    storage_root: Path,
    *,
    project_id: str,
    sample_id: str,
    task_id: str | None = None,
) -> Path | None:
    if not _eval_enabled():
        return None

    try:
        from evaluation.observability_rollup import build_observability_summary

        analysis_root = storage_root / "projects" / project_id / "samples" / sample_id / "analysis"
        checkpoint_path = analysis_root / "checkpoint.json"
        checkpoint: dict[str, Any] | None = None
        if checkpoint_path.is_file():
            try:
                raw = json.loads(checkpoint_path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    checkpoint = raw
            except (OSError, json.JSONDecodeError):
                checkpoint = None

        observability = build_observability_summary(
            storage_root,
            project_id=project_id,
            generation_id=None,
            task_id=task_id,
            checkpoint=checkpoint,
        )
        observability.setdefault("notes", []).append("scope=sample_analysis")

        profile = {
            "inputMode": "sample_migration",
            "enabledModules": ["core"],
            "referenceStructureId": sample_id,
        }

        report: dict[str, Any] = {
            "version": "1.0",
            "generationId": f"sample-{sample_id}",
            "projectId": project_id,
            "taskId": task_id,
            "evaluatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "partial": False,
            "profile": profile,
            "verdict": {"status": "pass", "blockingIssues": [], "warnings": []},
            "scores": {"core": {"weighted": 0.0, "technical": 0.0, "plan": 0.0, "perceptual": 0.0}},
            "modules": {"sample_analysis": {"scope": "sample", "sampleId": sample_id}},
            "observability": observability,
        }
        path = analysis_root / "evaluation-report.json"
        analysis_root.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        return path
    except Exception as exc:
        log_evaluation_failure(
            "sample_analysis",
            project_id=project_id,
            entity_id=sample_id,
            exc=exc,
        )
        return None
