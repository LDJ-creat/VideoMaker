from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.validation.schema_loader import validate_contract


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def script_draft_path(generation_root: Path) -> Path:
    return generation_root / "script-draft.json"


def empty_script_draft(
    *,
    generation_id: str,
    project_id: str,
    variant: str,
    duration_target_sec: float | None = None,
) -> dict[str, Any]:
    draft: dict[str, Any] = {
        "generationId": generation_id,
        "projectId": project_id,
        "variant": variant,
        "masterNarration": "",
        "masterNarrationStatus": "draft",
        "storyboard": [],
        "storyboardStatus": "draft",
    }
    if duration_target_sec is not None:
        draft["durationTargetSec"] = round(float(duration_target_sec), 2)
    return draft


def load_script_draft(generation_root: Path) -> dict[str, Any] | None:
    path = script_draft_path(generation_root)
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def save_script_draft(generation_root: Path, draft: dict[str, Any]) -> dict[str, Any]:
    validation = validate_contract("script-draft", draft)
    if not validation.valid:
        raise ValueError(f"Invalid ScriptDraft payload: {validation.errors}")
    path = script_draft_path(generation_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(draft, ensure_ascii=False, indent=2), encoding="utf-8")
    return draft


def master_is_approved(draft: dict[str, Any] | None) -> bool:
    return isinstance(draft, dict) and draft.get("masterNarrationStatus") == "approved"


def storyboard_is_approved(draft: dict[str, Any] | None) -> bool:
    return isinstance(draft, dict) and draft.get("storyboardStatus") == "approved"


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
    merged["storyboardStatus"] = "approved"
    merged["storyboardApprovedAt"] = _utc_now_iso()
    merged["approvedBy"] = approved_by
    return merged
