from __future__ import annotations

from pathlib import Path
from typing import Any

from evaluation.artifacts import read_json, storyboard_scenes


def score_plan_quality(generation_root: Path) -> dict[str, Any]:
    issues: list[str] = []
    score = 100.0

    plan = read_json(generation_root / "generation-plan.json") or {}
    gap = read_json(generation_root / "gap-report.json") or {}
    scenes = storyboard_scenes(plan)

    if not scenes:
        issues.append("missing_storyboard_scenes")
        score -= 25

    weak = list(gap.get("weakSlots") or gap.get("weak") or [])
    missing = list(gap.get("missingSlots") or gap.get("missing") or [])
    if weak or missing:
        unresolved = 0
        actions = list(plan.get("completionActions") or plan.get("completion") or [])
        action_slots = {
            str(item.get("slotId"))
            for item in actions
            if isinstance(item, dict) and item.get("slotId")
        }
        for slot in [*weak, *missing]:
            slot_id = slot.get("slotId") if isinstance(slot, dict) else slot
            if slot_id and str(slot_id) not in action_slots:
                unresolved += 1
        if unresolved:
            issues.append(f"unresolved_gaps:{unresolved}")
            score -= min(30, unresolved * 10)

    text_heavy = sum(
        1
        for scene in scenes
        if str(scene.get("role") or "").lower() in {"subtitle", "packaging", "text"}
    )
    if scenes and text_heavy / len(scenes) > 0.6:
        issues.append("text_heavy_storyboard")
        score -= 15

    reviews_dir = generation_root / "material-reviews"
    passed = 0
    total = 0
    if reviews_dir.is_dir():
        for report_path in reviews_dir.glob("*/report.json"):
            report = read_json(report_path)
            if not isinstance(report, dict):
                continue
            total += 1
            if report.get("approved"):
                passed += 1
    if total:
        ratio = passed / total
        if ratio < 1.0:
            issues.append(f"material_review_pass_ratio:{ratio:.2f}")
            score -= (1.0 - ratio) * 20

    score = max(0.0, min(100.0, score))
    return {
        "score": round(score, 1),
        "issues": issues,
        "sceneCount": len(scenes),
        "materialReviewPassRatio": round(passed / total, 2) if total else None,
    }
