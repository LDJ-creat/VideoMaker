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
class ModelCallLog:
    call_kind: str
    profile: str
    model: str
    driver: str
    output_valid: bool
    latency_ms: float
    task_id: str | None = None
    generation_id: str | None = None
    slot_id: str | None = None
    agent_name: str | None = None
    turn: int | None = None
    job_id: str | None = None
    input_payload: Any = None
    output_payload: Any = None
    token_usage: dict[str, float] | None = None
    usage_units: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    run_id: str | None = None
    created_at: str | None = None

    def to_payload(self, *, project_id: str) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.run_id or str(uuid.uuid4()),
            "callKind": self.call_kind,
            "profile": self.profile,
            "model": self.model,
            "driver": self.driver,
            "projectId": project_id,
            "outputValid": self.output_valid,
            "latencyMs": round(self.latency_ms, 3),
            "createdAt": self.created_at or _utc_now_iso(),
        }
        if self.task_id:
            payload["taskId"] = self.task_id
        if self.generation_id:
            payload["generationId"] = self.generation_id
        if self.slot_id:
            payload["slotId"] = self.slot_id
        if self.agent_name:
            payload["agentName"] = self.agent_name
        if self.turn is not None:
            payload["turn"] = self.turn
        if self.job_id:
            payload["jobId"] = self.job_id
        if self.input_payload is not None:
            payload["input"] = self.input_payload
        if self.output_payload is not None:
            payload["output"] = self.output_payload
        if self.token_usage:
            payload["tokenUsage"] = self.token_usage
        if self.usage_units:
            payload["usageUnits"] = self.usage_units
        if self.error:
            payload["error"] = self.error
        return payload


class ModelCallStore:
    def __init__(self, storage_root: Path) -> None:
        self._storage_root = Path(storage_root)

    @property
    def storage_root(self) -> Path:
        return self._storage_root

    def record(self, *, project_id: str, log: ModelCallLog) -> Path:
        payload = log.to_payload(project_id=project_id)
        validation = validate_contract("model-call-log", payload)
        if not validation.valid:
            raise ValueError(f"Invalid ModelCallLog payload: {validation.errors}")

        log_dir = (
            self._storage_root
            / "projects"
            / project_id
            / "logs"
            / "model-calls"
        )
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / f"{payload['id']}.json"
        log_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return log_path

    def update_output_valid(
        self,
        *,
        project_id: str,
        call_id: str,
        output_valid: bool,
        error: dict[str, Any] | None = None,
    ) -> bool:
        log_path = (
            self._storage_root
            / "projects"
            / project_id
            / "logs"
            / "model-calls"
            / f"{call_id}.json"
        )
        if not log_path.is_file():
            return False
        try:
            payload = json.loads(log_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False
        payload["outputValid"] = output_valid
        if error is not None:
            payload["error"] = error
        validation = validate_contract("model-call-log", payload)
        if not validation.valid:
            return False
        log_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return True
