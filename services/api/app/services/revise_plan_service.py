from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from knowledge.paths import validate_storage_segment

REVISE_PATCH_CONTEXT_FILE = "revise-patch-context.json"
_REPO_ROOT = Path(__file__).resolve().parents[4]


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _validate_project_id(project_id: str) -> str:
    return validate_storage_segment(project_id, field="project_id")


def _validate_generation_id(generation_id: str) -> str:
    return validate_storage_segment(generation_id, field="generation_id")


def _validate_plan_id(plan_id: str) -> str:
    return validate_storage_segment(plan_id, field="plan_id")


def validate_revise_plan(plan: dict[str, Any]) -> None:
    import jsonschema

    schema_path = _REPO_ROOT / "packages" / "contracts" / "schemas" / "revise-plan.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    try:
        jsonschema.validate(instance=plan, schema=schema)
    except jsonschema.ValidationError as exc:
        raise ValueError(f"Invalid RevisePlan payload: {exc.message}") from exc


def validate_revise_session(session: dict[str, Any]) -> None:
    import jsonschema

    schema_path = _REPO_ROOT / "packages" / "contracts" / "schemas" / "revise-session.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    try:
        jsonschema.validate(instance=session, schema=schema)
    except jsonschema.ValidationError as exc:
        raise ValueError(f"Invalid ReviseSession payload: {exc.message}") from exc


def generation_root(storage_root: Path, project_id: str, generation_id: str) -> Path:
    project_id = _validate_project_id(project_id)
    generation_id = _validate_generation_id(generation_id)
    return storage_root / "projects" / project_id / "generations" / generation_id


def session_path(storage_root: Path, project_id: str, generation_id: str) -> Path:
    return generation_root(storage_root, project_id, generation_id) / "revise-session.json"


def plan_path(storage_root: Path, project_id: str, generation_id: str, plan_id: str) -> Path:
    plan_id = _validate_plan_id(plan_id)
    return (
        generation_root(storage_root, project_id, generation_id)
        / "revise-plans"
        / plan_id
        / "plan.json"
    )


def patch_context_path(storage_root: Path, project_id: str, generation_id: str) -> Path:
    return generation_root(storage_root, project_id, generation_id) / REVISE_PATCH_CONTEXT_FILE


def write_revise_patch_context(
    storage_root: Path,
    project_id: str,
    generation_id: str,
    *,
    plan_id: str,
    task_id: str,
) -> None:
    path = patch_context_path(storage_root, project_id, generation_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "mode": "execute_revise_patch",
                "planId": _validate_plan_id(plan_id),
                "taskId": task_id,
                "sourceGenerationId": _validate_generation_id(generation_id),
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def load_revise_patch_context(
    storage_root: Path,
    project_id: str,
    generation_id: str,
) -> dict[str, Any] | None:
    path = patch_context_path(storage_root, project_id, generation_id)
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def clear_revise_patch_context(
    storage_root: Path,
    project_id: str,
    generation_id: str,
) -> None:
    path = patch_context_path(storage_root, project_id, generation_id)
    if path.is_file():
        path.unlink()


def load_session(storage_root: Path, project_id: str, generation_id: str) -> dict[str, Any] | None:
    path = session_path(storage_root, project_id, generation_id)
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def save_session(
    storage_root: Path,
    project_id: str,
    generation_id: str,
    session: dict[str, Any],
    *,
    validate: bool = True,
) -> None:
    if validate:
        validate_revise_session(session)
    path = session_path(storage_root, project_id, generation_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    session["updatedAt"] = _utc_now_iso()
    path.write_text(json.dumps(session, indent=2, ensure_ascii=False), encoding="utf-8")


def create_or_load_session(
    storage_root: Path,
    project_id: str,
    generation_id: str,
    *,
    new_session: bool = False,
) -> dict[str, Any]:
    if new_session:
        existing = load_session(storage_root, project_id, generation_id)
        if existing is not None and existing.get("status") != "archived":
            existing["status"] = "archived"
            save_session(storage_root, project_id, generation_id, existing)
        return {
            "sessionId": str(uuid.uuid4()),
            "sourceGenerationId": _validate_generation_id(generation_id),
            "status": "active",
            "turns": [],
            "updatedAt": _utc_now_iso(),
        }
    existing = load_session(storage_root, project_id, generation_id)
    if existing is not None and existing.get("status") != "archived":
        return existing
    return {
        "sessionId": str(uuid.uuid4()),
        "sourceGenerationId": _validate_generation_id(generation_id),
        "status": "active",
        "turns": [],
        "updatedAt": _utc_now_iso(),
    }


def load_plan(
    storage_root: Path,
    project_id: str,
    generation_id: str,
    plan_id: str,
) -> dict[str, Any] | None:
    _validate_plan_id(plan_id)
    path = plan_path(storage_root, project_id, generation_id, plan_id)
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def save_plan(
    storage_root: Path,
    project_id: str,
    generation_id: str,
    plan: dict[str, Any],
    *,
    validate: bool = True,
) -> None:
    plan_id = str(plan.get("planId") or "")
    if not plan_id:
        raise ValueError("planId is required")
    _validate_plan_id(plan_id)
    if validate:
        validate_revise_plan(plan)
    path = plan_path(storage_root, project_id, generation_id, plan_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")


def update_turn_status(
    session: dict[str, Any],
    plan_id: str,
    status: str,
) -> None:
    turns = session.get("turns")
    if not isinstance(turns, list):
        return
    for turn in turns:
        if isinstance(turn, dict) and turn.get("planId") == plan_id:
            turn["status"] = status


def mark_plan_executing(
    storage_root: Path,
    project_id: str,
    source_generation_id: str,
    plan: dict[str, Any],
    *,
    task_id: str,
    result_generation_id: str | None = None,
) -> dict[str, Any]:
    plan = dict(plan)
    plan["status"] = "executing"
    plan["resultTaskId"] = task_id
    if result_generation_id is not None:
        plan["resultGenerationId"] = result_generation_id
    save_plan(storage_root, project_id, source_generation_id, plan)
    session = load_session(storage_root, project_id, source_generation_id)
    if session is not None:
        update_turn_status(session, str(plan["planId"]), "executing")
        save_session(storage_root, project_id, source_generation_id, session)
    return plan


def mark_plan_executed(
    storage_root: Path,
    project_id: str,
    source_generation_id: str,
    plan_id: str,
    *,
    result_generation_id: str,
    task_id: str,
) -> None:
    plan = load_plan(storage_root, project_id, source_generation_id, plan_id)
    if plan is None:
        return
    plan["status"] = "executed"
    plan["executedAt"] = _utc_now_iso()
    plan["resultGenerationId"] = result_generation_id
    plan["resultTaskId"] = task_id
    save_plan(storage_root, project_id, source_generation_id, plan)
    session = load_session(storage_root, project_id, source_generation_id)
    if session is not None:
        update_turn_status(session, plan_id, "executed")
        save_session(storage_root, project_id, source_generation_id, session)


def mark_plan_execution_failed(
    storage_root: Path,
    project_id: str,
    source_generation_id: str,
    plan_id: str,
) -> None:
    plan = load_plan(storage_root, project_id, source_generation_id, plan_id)
    if plan is None:
        return
    plan["status"] = "approved"
    save_plan(storage_root, project_id, source_generation_id, plan)
    session = load_session(storage_root, project_id, source_generation_id)
    if session is not None:
        update_turn_status(session, plan_id, "failed")
        save_session(storage_root, project_id, source_generation_id, session)


def find_latest_draft_plan(
    storage_root: Path,
    project_id: str,
    generation_id: str,
    session: dict[str, Any],
) -> dict[str, Any] | None:
    for plan in list_recent_plans(storage_root, project_id, generation_id, session, limit=10):
        if plan.get("status") == "draft":
            return plan
    return None


def append_session_turn(session: dict[str, Any], turn: dict[str, Any]) -> None:
    turns = session.setdefault("turns", [])
    if not isinstance(turns, list):
        turns = []
        session["turns"] = turns
    turns.append(turn)


def supersede_draft_plans(
    storage_root: Path,
    project_id: str,
    generation_id: str,
    session: dict[str, Any],
) -> None:
    turns = session.get("turns")
    if not isinstance(turns, list):
        return
    for turn in turns:
        if not isinstance(turn, dict):
            continue
        if turn.get("status") != "planned":
            continue
        plan_id = str(turn.get("planId") or "")
        if not plan_id:
            continue
        plan = load_plan(storage_root, project_id, generation_id, plan_id)
        if plan is None or plan.get("status") != "draft":
            continue
        plan["status"] = "superseded"
        save_plan(storage_root, project_id, generation_id, plan)
        turn["status"] = "cancelled"


def list_recent_plans(
    storage_root: Path,
    project_id: str,
    generation_id: str,
    session: dict[str, Any],
    limit: int = 5,
) -> list[dict[str, Any]]:
    turns = session.get("turns")
    if not isinstance(turns, list):
        return []
    plans: list[dict[str, Any]] = []
    for turn in reversed(turns):
        if not isinstance(turn, dict):
            continue
        plan_id = str(turn.get("planId") or "")
        if not plan_id:
            continue
        plan = load_plan(storage_root, project_id, generation_id, plan_id)
        if plan is not None:
            plans.append(plan)
        if len(plans) >= limit:
            break
    return plans
