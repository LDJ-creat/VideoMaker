from __future__ import annotations

from pathlib import Path
from typing import Any

from evaluation.artifacts import read_json, storyboard_scenes


def score_knowledge_fit(generation_root: Path, *, knowledge_entry_id: str | None) -> dict[str, Any]:
    issues: list[str] = []
    score = 80.0

    structure = read_json(generation_root / "video-structure.json") or {}
    analysis_quality = structure.get("analysisQuality") if isinstance(structure.get("analysisQuality"), dict) else {}
    if analysis_quality.get("promoteReady") is False:
        issues.append("structure_not_promote_ready")
        score -= 20

    warnings = list(analysis_quality.get("warnings") or [])
    critical = [w for w in warnings if str(w).startswith("critical:")]
    if critical:
        issues.append(f"critical_structure_warnings:{len(critical)}")
        score -= min(25, len(critical) * 5)

    plan = read_json(generation_root / "generation-plan.json") or {}
    scene_count = len(storyboard_scenes(plan))
    ref_slots = len(structure.get("slots") or [])
    if ref_slots and scene_count < max(1, int(ref_slots * 0.5)):
        issues.append("sparse_storyboard_vs_template")
        score -= 15

    score = max(0.0, min(100.0, score))
    result: dict[str, Any] = {
        "weighted": round(score, 1),
        "issues": issues,
        "sceneCount": scene_count,
        "templateSlotCount": ref_slots,
    }
    if knowledge_entry_id:
        result["knowledgeEntryId"] = knowledge_entry_id
    return result
