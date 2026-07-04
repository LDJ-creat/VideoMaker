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
]


def _resolve_gateway_store(
    gateway: Any | None,
    task_context: TaskContext | None,
    *,
    database_path: str | Path | None = None,
    storage_root: str | Path | None = None,
) -> Any | None:
    if gateway is not None and hasattr(gateway, "store"):
        store = getattr(gateway, "store", None)
        if store is not None:
            return store
    db_path = (
        str(database_path).strip()
        if database_path is not None
        else os.environ.get("VM_DATABASE_PATH", "").strip()
    )
    root: str | None = None
    if task_context is not None:
        root = str(task_context.storage_root)
    elif storage_root is not None:
        root = str(storage_root)
    if db_path and root:
        from model_gateway.store import ModelGatewayStore

        return ModelGatewayStore(Path(db_path), Path(root))
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
