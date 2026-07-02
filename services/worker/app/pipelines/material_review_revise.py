from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from material_review_revise_context import (
    build_material_review_revise_context_payload,
    load_material_review_revise_context,
)

from app.pipelines.material_review_state import (
    load_material_review_state,
    save_material_review_state,
)

__all__ = [
    "build_material_review_revise_context_payload",
    "load_material_review_revise_context",
    "material_review_revise_context_payload",
    "reset_material_review_for_revise_fork",
]


def reset_material_review_for_revise_fork(
    generation_root: Path,
    affected_slot_ids: set[str],
    *,
    full_reset: bool = False,
) -> None:
    """Reset material review state after fork seed; unaffected slots keep inherited reports."""
    state_path = generation_root / "material-review-state.json"
    if not state_path.is_file():
        return

    state = load_material_review_state(generation_root)
    if not isinstance(state, dict):
        return

    if full_reset:
        state["status"] = "draft"
        state["slots"] = {}
        state.pop("approvedAt", None)
        state.pop("approvedBy", None)
        reviews_root = generation_root / "material-reviews"
        if reviews_root.is_dir():
            shutil.rmtree(reviews_root)
        save_material_review_state(generation_root, state)
        return

    if not affected_slot_ids:
        return

    slots = dict(state.get("slots") or {})
    for slot_id in sorted(affected_slot_ids):
        slots[slot_id] = {"status": "pending"}
        report_dir = generation_root / "material-reviews" / slot_id
        if report_dir.is_dir():
            shutil.rmtree(report_dir)

    state["slots"] = slots
    if state.get("status") == "approved":
        state["status"] = "draft"
        state.pop("approvedAt", None)
        state.pop("approvedBy", None)
    save_material_review_state(generation_root, state)


def material_review_revise_context_payload(
    *,
    source_generation_id: str,
    revise_context: Any,
) -> dict[str, Any]:
    return build_material_review_revise_context_payload(
        source_generation_id=source_generation_id,
        material_scope=str(getattr(revise_context, "material_scope", "") or ""),
        affected_slot_ids=list(getattr(revise_context, "affected_slot_ids", None) or []),
        affected_pipeline_stages=list(
            getattr(revise_context, "affected_pipeline_stages", None) or []
        ),
    )
