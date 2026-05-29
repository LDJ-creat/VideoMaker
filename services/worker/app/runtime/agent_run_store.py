from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json
import uuid

from app.validation.schema_loader import validate_contract


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass
class AgentRunLog:
    agent_name: str
    prompt_version: str
    model: str
    task: str
    input_summary: str
    output_valid: bool
    latency_ms: float
    task_id: str | None = None
    generation_id: str | None = None
    validation_errors: list[str] = field(default_factory=list)
    token_usage: dict[str, float] | None = None
    run_id: str | None = None
    created_at: str | None = None

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.run_id or str(uuid.uuid4()),
            "agentName": self.agent_name,
            "promptVersion": self.prompt_version,
            "model": self.model,
            "task": self.task,
            "inputSummary": self.input_summary,
            "outputValid": self.output_valid,
            "latencyMs": round(self.latency_ms, 3),
            "createdAt": self.created_at or _utc_now_iso(),
        }
        if self.task_id:
            payload["taskId"] = self.task_id
        if self.generation_id:
            payload["generationId"] = self.generation_id
        if self.validation_errors:
            payload["validationErrors"] = self.validation_errors
        if self.token_usage:
            payload["tokenUsage"] = self.token_usage
        return payload


class AgentRunStore:
    def __init__(self, storage_root: Path) -> None:
        self._storage_root = Path(storage_root)

    @property
    def storage_root(self) -> Path:
        return self._storage_root

    def record(self, *, project_id: str, log: AgentRunLog) -> Path:
        payload = log.to_payload()
        validation = validate_contract("agent-run-log", payload)
        if not validation.valid:
            raise ValueError(f"Invalid AgentRunLog payload: {validation.errors}")

        log_dir = (
            self._storage_root
            / "projects"
            / project_id
            / "logs"
            / "agent-runs"
        )
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / f"{payload['id']}.json"
        log_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return log_path
