from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from app.pipelines.material_gate_finalize import (
    all_visual_slots_ready,
    finalize_slot_material_gate,
    finalize_visual_material_gate,
    persist_slot_material_review,
    finalize_visual_material_reviews,
)
from app.pipelines.material_review import material_review_enabled
from app.runtime.task_context import TaskContext

__all__ = [
    "all_visual_slots_ready",
    "finalize_slot_material_gate",
    "finalize_visual_material_gate",
    "persist_slot_material_review",
    "finalize_visual_material_reviews",
    "_build_author_payload",
    "_resolve_gateway_store",
    "infer_storage_root_from_generation_root",
    "resolve_database_path",
    "resolve_storage_root_path",
]


def infer_storage_root_from_generation_root(generation_root: Path | None) -> Path | None:
    """Resolve storage root from .../storage/projects/{projectId}/generations/{generationId}."""
    if generation_root is None:
        return None
    resolved = generation_root.resolve()
    for parent in resolved.parents:
        if parent.name == "projects":
            return parent.parent
    return None


def resolve_storage_root_path(
    explicit: str | Path | None = None,
    *,
    generation_root: Path | None = None,
    task_context: TaskContext | None = None,
) -> Path | None:
    if explicit is not None:
        text = str(explicit).strip()
        if text:
            return Path(text)
    env_root = os.environ.get("VM_STORAGE_ROOT", "").strip()
    if env_root:
        return Path(env_root)
    if task_context is not None:
        return Path(task_context.storage_root)
    return infer_storage_root_from_generation_root(generation_root)


def resolve_database_path(
    explicit: str | Path | None = None,
    *,
    storage_root: Path | str | None = None,
) -> Path | None:
    if explicit is not None:
        text = str(explicit).strip()
        if text:
            return Path(text)
    env_db = os.environ.get("VM_DATABASE_PATH", "").strip()
    if env_db:
        return Path(env_db)
    if storage_root is not None:
        candidate = Path(storage_root) / "videomaker.sqlite3"
        if candidate.is_file():
            return candidate
    repo_root = os.environ.get("VIDEOMAKER_REPO_ROOT", "").strip()
    if repo_root:
        for relative in (
            Path("services/api/storage/videomaker.sqlite3"),
            Path("storage/videomaker.sqlite3"),
        ):
            candidate = Path(repo_root) / relative
            if candidate.is_file():
                return candidate
    return None


def _resolve_gateway_store(
    gateway: Any | None,
    task_context: TaskContext | None,
    *,
    database_path: str | Path | None = None,
    storage_root: str | Path | None = None,
    generation_root: Path | None = None,
) -> Any | None:
    if gateway is not None and hasattr(gateway, "store"):
        store = getattr(gateway, "store", None)
        if store is not None:
            return store
    root = resolve_storage_root_path(
        storage_root,
        generation_root=generation_root,
        task_context=task_context,
    )
    db_path = resolve_database_path(database_path, storage_root=root)
    if db_path is not None and root is not None:
        from model_gateway.store import ModelGatewayStore

        return ModelGatewayStore(db_path, root)
    return None


def _build_author_payload(
    *,
    project_id: str,
    generation_id: str,
    generation_root: Path,
    task_id: str | None,
    slot_id: str,
    slot_timing: dict[str, Any] | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "projectId": project_id,
        "generationId": generation_id,
        "generationRoot": str(generation_root),
        "slotId": slot_id,
        "slot": {"id": slot_id},
    }
    if task_id:
        payload["taskId"] = task_id
    if slot_timing:
        payload["slotTiming"] = slot_timing

    task_path = generation_root / "acp-author" / slot_id / "task.json"
    if task_path.is_file():
        try:
            task_payload = json.loads(task_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            task_payload = None
        if isinstance(task_payload, dict):
            for key in (
                "slot",
                "finishBrief",
                "compositionAuthorBrief",
                "renderPolicy",
                "visualStyleBible",
                "renderTarget",
                "variantOverrides",
                "brandColors",
                "layoutDirective",
                "fieldSemantics",
                "materialEditMode",
                "editInstruction",
            ):
                if key in task_payload and task_payload[key] is not None:
                    payload[key] = task_payload[key]
    return payload
