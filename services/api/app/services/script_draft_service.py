from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def generation_root(storage_root: Path, project_id: str, generation_id: str) -> Path:
    return storage_root / "projects" / project_id / "generations" / generation_id


def clear_narration_preview_artifacts(storage_root: Path, project_id: str, generation_id: str) -> None:
    root = generation_root(storage_root, project_id, generation_id)
    preview_json = root / "narration-preview.json"
    preview_wav = root / "preview" / "master.wav"
    if preview_json.is_file():
        preview_json.unlink()
    if preview_wav.is_file():
        preview_wav.unlink()


def script_draft_path(storage_root: Path, project_id: str, generation_id: str) -> Path:
    return generation_root(storage_root, project_id, generation_id) / "script-draft.json"


def load_script_draft(storage_root: Path, project_id: str, generation_id: str) -> dict[str, Any]:
    path = script_draft_path(storage_root, project_id, generation_id)
    if not path.is_file():
        raise FileNotFoundError("script-draft.json not found")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Invalid script draft payload")
    return payload


def save_script_draft(
    storage_root: Path,
    project_id: str,
    generation_id: str,
    draft: dict[str, Any],
) -> dict[str, Any]:
    from app.services.contract_validation import validate_script_draft

    validation = validate_script_draft(draft)
    if not validation.valid:
        details = "; ".join(f"{item.path}: {item.message}" for item in validation.errors[:5])
        raise ValueError(f"Invalid ScriptDraft payload: {details}")
    path = script_draft_path(storage_root, project_id, generation_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(draft, ensure_ascii=False, indent=2), encoding="utf-8")
    return draft


def approve_master_draft(draft: dict[str, Any], *, approved_by: str = "user") -> dict[str, Any]:
    merged = dict(draft)
    master = str(merged.get("masterNarration") or "").strip()
    if not master:
        raise ValueError("masterNarration must not be empty before approval")
    merged["masterNarration"] = master
    merged["masterNarrationStatus"] = "approved"
    merged["masterApprovedAt"] = _utc_now_iso()
    merged["approvedBy"] = approved_by
    return merged


def approve_storyboard_draft(draft: dict[str, Any], *, approved_by: str = "user") -> dict[str, Any]:
    merged = dict(draft)
    storyboard = merged.get("storyboard")
    if not isinstance(storyboard, list) or not storyboard:
        raise ValueError("storyboard must not be empty before approval")
    if merged.get("masterNarrationStatus") != "approved":
        raise ValueError("Master narration must be approved before storyboard approval")
    merged["storyboardStatus"] = "approved"
    merged["storyboardApprovedAt"] = _utc_now_iso()
    merged["approvedBy"] = approved_by
    return merged


def validate_nl_revise_gate(
    *,
    scope: str,
    draft: dict[str, Any],
    task_stage: str | None,
) -> None:
    if scope == "master":
        if task_stage != "awaiting_master_review":
            raise ValueError("NL revise for master requires task stage awaiting_master_review")
        if draft.get("masterNarrationStatus") == "approved":
            raise ValueError("Master narration already approved")
        return
    if scope == "storyboard":
        if task_stage != "awaiting_storyboard_review":
            raise ValueError("NL revise for storyboard requires task stage awaiting_storyboard_review")
        if draft.get("masterNarrationStatus") != "approved":
            raise ValueError("Master narration must be approved before storyboard NL revise")
        if draft.get("storyboardStatus") == "approved":
            raise ValueError("Storyboard already approved")
        return
    raise ValueError(f"Invalid NL revise scope: {scope}")
