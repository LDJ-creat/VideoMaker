from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


MATERIAL_REVIEW_STATE_FILENAME = "material-review-state.json"
MATERIAL_SLOT_REVISE_QUEUE_FILENAME = "material-slot-revise-queue.json"


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def material_review_state_path(generation_root: Path) -> Path:
    return generation_root / MATERIAL_REVIEW_STATE_FILENAME


def material_slot_revise_queue_path(generation_root: Path) -> Path:
    return generation_root / MATERIAL_SLOT_REVISE_QUEUE_FILENAME


def load_material_review_state(generation_root: Path) -> dict[str, Any] | None:
    path = material_review_state_path(generation_root)
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def save_material_review_state(generation_root: Path, state: dict[str, Any]) -> None:
    path = material_review_state_path(generation_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def material_is_approved(generation_root: Path) -> bool:
    state = load_material_review_state(generation_root)
    return isinstance(state, dict) and state.get("status") == "approved"


def ensure_material_review_state(
    *,
    generation_root: Path,
    generation_id: str,
    project_id: str,
    variant: str,
) -> dict[str, Any]:
    existing = load_material_review_state(generation_root)
    if isinstance(existing, dict) and existing.get("generationId") == generation_id:
        return existing
    state = {
        "generationId": generation_id,
        "projectId": project_id,
        "variant": variant,
        "status": "draft",
        "slots": {},
    }
    save_material_review_state(generation_root, state)
    return state


def update_slot_review_entry(
    generation_root: Path,
    *,
    slot_id: str,
    report: dict[str, Any],
    spec_uri: str | None = None,
    preview_artifact_ref: dict[str, Any] | None = None,
) -> dict[str, Any]:
    state = load_material_review_state(generation_root)
    if not isinstance(state, dict):
        raise FileNotFoundError("material-review-state.json missing")
    slots = dict(state.get("slots") or {})
    entry = dict(slots.get(slot_id) or {})
    if report.get("reviewUnavailable"):
        entry["status"] = "review_unavailable"
    elif report.get("hardGateFailed"):
        entry["status"] = "hard_gate_failed"
        entry["hardGateFailed"] = True
    elif report.get("reviewInputs", {}).get("mode") == "skipped" and report.get("approved"):
        entry["status"] = "skipped"
    else:
        entry["status"] = "agent_passed" if report.get("approved") else "agent_failed"
    if spec_uri:
        entry["specUri"] = spec_uri
    if preview_artifact_ref:
        entry["previewArtifactRef"] = preview_artifact_ref
    entry["latestReportUri"] = f"material-reviews/{slot_id}/report.json"
    entry["agentReviewRounds"] = int(report.get("agentReviewRound") or entry.get("agentReviewRounds") or 0)
    slots[slot_id] = entry
    state["slots"] = slots
    save_material_review_state(generation_root, state)
    return state


def approve_material_state(generation_root: Path, *, approved_by: str = "user") -> dict[str, Any]:
    state = load_material_review_state(generation_root)
    if not isinstance(state, dict):
        raise FileNotFoundError("material-review-state.json missing")
    if state.get("status") == "approved":
        return state
    state["status"] = "approved"
    state["approvedAt"] = _utc_now_iso()
    state["approvedBy"] = approved_by
    save_material_review_state(generation_root, state)
    return state


def load_material_slot_revise_queue(generation_root: Path) -> dict[str, Any] | None:
    path = material_slot_revise_queue_path(generation_root)
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def write_material_slot_revise_queue(generation_root: Path, payload: dict[str, Any]) -> None:
    path = material_slot_revise_queue_path(generation_root)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def clear_material_slot_revise_queue(generation_root: Path) -> None:
    path = material_slot_revise_queue_path(generation_root)
    if path.is_file():
        path.unlink()
