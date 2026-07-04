from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from evaluation.artifacts import find_generation_mp4, read_json, target_duration_sec
from evaluation.knowledge_fit_scorer import score_knowledge_fit
from evaluation.migration_scorer import score_migration
from evaluation.observability_rollup import build_observability_summary
from evaluation.perceptual_proxy import score_perceptual_proxy
from evaluation.plan_quality import score_plan_quality
from evaluation.price_table import estimate_cost_usd, load_price_table
from evaluation.profile_resolver import resolve_evaluation_profile
from evaluation.schemas import validate_evaluation_report
import os


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _resolve_price_table() -> dict[str, Any]:
    custom = os.getenv("VIDEOMAKER_EVAL_PRICE_TABLE", "").strip()
    if custom:
        return load_price_table(Path(custom))
    return load_price_table()


def _schema_strict_enabled() -> bool:
    return os.getenv("VIDEOMAKER_EVAL_SCHEMA_STRICT", "false").strip().lower() == "true"


def build_evaluation_report(
    storage_root: Path,
    *,
    project_id: str,
    generation_id: str,
    task_id: str | None = None,
    variant_id: str | None = None,
    partial: bool = False,
    task_events: list[dict[str, Any]] | None = None,
    technical_qa: dict[str, Any] | None = None,
) -> dict[str, Any]:
    generation_root = storage_root / "projects" / project_id / "generations" / generation_id
    checkpoint = read_json(generation_root / "checkpoint.json")
    profile = resolve_evaluation_profile(generation_root, variant_id=variant_id)

    observability = build_observability_summary(
        storage_root,
        project_id=project_id,
        generation_id=generation_id,
        task_id=task_id,
        checkpoint=checkpoint if isinstance(checkpoint, dict) else None,
        task_events=task_events,
    )
    cost = estimate_cost_usd(observability.get("usageByCategory") or {}, _resolve_price_table())
    if cost:
        observability["estimatedCostUsd"] = cost

    plan_mod = score_plan_quality(generation_root)
    perceptual_mod = score_perceptual_proxy(generation_root)
    if technical_qa is not None:
        technical_score: float | None = float(technical_qa.get("score") or 0.0)
    elif partial:
        technical_score = None
    else:
        technical_score = 0.0

    scores: dict[str, Any] = {
        "core": {
            "technical": round(technical_score, 1) if technical_score is not None else None,
            "plan": plan_mod["score"],
            "perceptual": perceptual_mod["score"],
        }
    }
    tech_weight = technical_score if technical_score is not None else 0.0
    core_weighted = (
        tech_weight * 0.35
        + scores["core"]["plan"] * 0.35
        + scores["core"]["perceptual"] * 0.30
    )
    scores["core"]["weighted"] = round(core_weighted, 1)

    modules: dict[str, Any] = {
        "plan_quality": plan_mod,
        "perceptual_proxy": perceptual_mod,
    }
    if technical_qa:
        modules["technical_qa"] = technical_qa

    blocking: list[str] = []
    warnings: list[str] = []
    if technical_qa:
        blocking.extend(list(technical_qa.get("blockingIssues") or []))
        warnings.extend(list(technical_qa.get("warnings") or []))
    warnings.extend(plan_mod.get("issues") or [])
    warnings.extend(perceptual_mod.get("issues") or [])

    enabled = set(profile.get("enabledModules") or [])
    reference_structure = (
        read_json(generation_root / "structure-scaled.json")
        or read_json(generation_root / "synthesized-structure.json")
        or read_json(generation_root / "video-structure.json")
    )
    if "migration" in enabled:
        migration = score_migration(generation_root, reference_structure)
        modules["migration"] = migration
        scores["migration"] = {"weighted": migration["weighted"], **migration}
        warnings.extend(migration.get("issues") or [])
    if "knowledge_fit" in enabled:
        knowledge = score_knowledge_fit(
            generation_root,
            knowledge_entry_id=profile.get("knowledgeEntryId"),
        )
        modules["knowledge_fit"] = knowledge
        scores["knowledgeFit"] = {"weighted": knowledge["weighted"], **knowledge}
        warnings.extend(knowledge.get("issues") or [])

    status = "partial" if partial else "pass"
    if blocking:
        status = "block"
    elif warnings:
        status = "warn" if status != "partial" else "partial"

    report: dict[str, Any] = {
        "version": "1.0",
        "generationId": generation_id,
        "projectId": project_id,
        "taskId": task_id,
        "evaluatedAt": _utc_now_iso(),
        "partial": partial,
        "profile": profile,
        "verdict": {
            "status": status,
            "blockingIssues": blocking,
            "warnings": warnings,
        },
        "scores": scores,
        "modules": modules,
        "observability": observability,
    }

    valid, errors = validate_evaluation_report(report)
    if not valid:
        if _schema_strict_enabled():
            raise ValueError(f"evaluation_report_schema_invalid: {'; '.join(errors[:5])}")
        report.setdefault("verdict", {}).setdefault("warnings", []).append(
            f"schema_validation:{'; '.join(errors[:3])}"
        )
    return report


def write_evaluation_report(
    storage_root: Path,
    report: dict[str, Any],
    *,
    partial: bool = False,
) -> Path:
    project_id = str(report.get("projectId") or "")
    generation_id = str(report.get("generationId") or "")
    generation_root = storage_root / "projects" / project_id / "generations" / generation_id
    generation_root.mkdir(parents=True, exist_ok=True)
    filename = "evaluation-report.partial.json" if partial else "evaluation-report.json"
    path = generation_root / filename
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return path
