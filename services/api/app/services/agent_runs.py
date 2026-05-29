from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TypedDict


class AgentRunSummary(TypedDict):
    id: str
    agentName: str
    model: str
    promptVersion: str
    outputValid: bool
    latencyMs: float
    createdAt: str


def list_agent_runs_for_generation(
    storage_root: Path,
    *,
    project_id: str,
    generation_id: str,
) -> list[AgentRunSummary]:
    log_dir = storage_root / "projects" / project_id / "logs" / "agent-runs"
    if not log_dir.is_dir():
        return []

    runs: list[AgentRunSummary] = []
    for path in log_dir.glob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if payload.get("generationId") != generation_id:
            continue
        try:
            runs.append(_to_summary(payload))
        except (KeyError, TypeError, ValueError):
            continue

    runs.sort(key=lambda item: item["createdAt"])
    return runs


def _to_summary(payload: dict[str, Any]) -> AgentRunSummary:
    return {
        "id": str(payload["id"]),
        "agentName": str(payload["agentName"]),
        "model": str(payload["model"]),
        "promptVersion": str(payload["promptVersion"]),
        "outputValid": bool(payload["outputValid"]),
        "latencyMs": float(payload["latencyMs"]),
        "createdAt": str(payload["createdAt"]),
    }
