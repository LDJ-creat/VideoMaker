from __future__ import annotations

from pathlib import Path
from typing import Any

from evaluation.artifacts import read_json, storyboard_scenes


def score_perceptual_proxy(generation_root: Path) -> dict[str, Any]:
    issues: list[str] = []
    score = 75.0

    reviews_dir = generation_root / "material-reviews"
    review_scores: list[float] = []
    if reviews_dir.is_dir():
        for report_path in reviews_dir.glob("*/report.json"):
            report = read_json(report_path)
            if not isinstance(report, dict):
                continue
            scores = report.get("scores")
            if isinstance(scores, dict):
                for value in scores.values():
                    if isinstance(value, (int, float)):
                        review_scores.append(float(value))
            elif isinstance(scores, (int, float)):
                review_scores.append(float(scores))

    if review_scores:
        avg = sum(review_scores) / len(review_scores)
        score = max(0.0, min(100.0, avg * 20.0 if avg <= 5 else avg))

    plan = read_json(generation_root / "generation-plan.json") or {}
    scenes = storyboard_scenes(plan)
    roles = [str(scene.get("role") or "") for scene in scenes]
    if roles and len(set(roles)) == 1:
        issues.append("uniform_scene_roles")
        score -= 10

    return {
        "scoreKind": "proxy",
        "score": round(score, 1),
        "issues": issues,
        "materialReviewScoreCount": len(review_scores),
    }
