from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TypedDict


class ModelCallSummary(TypedDict, total=False):
    id: str
    callKind: str
    profile: str
    model: str
    driver: str
    agentName: str
    slotId: str
    turn: int
    jobId: str
    outputValid: bool
    latencyMs: float
    createdAt: str
    taskId: str
    generationId: str
    tokenUsage: dict[str, Any]
    usageUnits: dict[str, Any]


def list_model_calls_for_generation(
    storage_root: Path,
    *,
    project_id: str,
    generation_id: str,
    kind: str | None = None,
) -> list[ModelCallSummary]:
    return _list_model_calls(
        storage_root,
        project_id=project_id,
        generation_id=generation_id,
        kind=kind,
    )


def list_model_calls_for_task(
    storage_root: Path,
    *,
    project_id: str,
    task_id: str,
    kind: str | None = None,
) -> list[ModelCallSummary]:
    return _list_model_calls(
        storage_root,
        project_id=project_id,
        task_id=task_id,
        kind=kind,
    )


def _list_model_calls(
    storage_root: Path,
    *,
    project_id: str,
    generation_id: str | None = None,
    task_id: str | None = None,
    kind: str | None = None,
) -> list[ModelCallSummary]:
    log_dir = storage_root / "projects" / project_id / "logs" / "model-calls"
    if not log_dir.is_dir():
        return []

    normalized_kind = _normalize_kind_filter(kind)
    runs: list[ModelCallSummary] = []
    for path in log_dir.glob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if generation_id is not None and payload.get("generationId") != generation_id:
            continue
        if task_id is not None and payload.get("taskId") != task_id:
            continue
        if normalized_kind is not None and payload.get("callKind") not in normalized_kind:
            continue
        try:
            runs.append(_to_summary(payload))
        except (KeyError, TypeError, ValueError):
            continue

    runs.sort(key=lambda item: item["createdAt"])
    return runs


def _normalize_kind_filter(kind: str | None) -> set[str] | None:
    if not kind:
        return None
    mapping = {
        "chat": {"chat_json", "chat_text", "chat_tools"},
        "image": {"image"},
        "video": {"video_submit", "video_poll"},
        "tts": {"tts"},
    }
    return mapping.get(kind.strip().lower(), {kind.strip()})


def _to_summary(payload: dict[str, Any]) -> ModelCallSummary:
    summary: ModelCallSummary = {
        "id": str(payload["id"]),
        "callKind": str(payload["callKind"]),
        "profile": str(payload["profile"]),
        "model": str(payload["model"]),
        "driver": str(payload["driver"]),
        "outputValid": bool(payload["outputValid"]),
        "latencyMs": float(payload["latencyMs"]),
        "createdAt": str(payload["createdAt"]),
    }
    for key in (
        "taskId",
        "generationId",
        "agentName",
        "slotId",
        "turn",
        "jobId",
    ):
        if payload.get(key) is not None:
            summary[key] = payload[key]  # type: ignore[literal-required]
    if isinstance(payload.get("tokenUsage"), dict):
        summary["tokenUsage"] = payload["tokenUsage"]  # type: ignore[typeddict-unknown-key]
    if isinstance(payload.get("usageUnits"), dict):
        summary["usageUnits"] = payload["usageUnits"]  # type: ignore[typeddict-unknown-key]
    return summary
