from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class ReactTraceRecorder(Protocol):
    @property
    def trace_dir(self) -> Path | None: ...

    def on_turn(
        self,
        turn: int,
        *,
        response: dict[str, Any],
        latency_ms: float | None = None,
    ) -> None: ...

    def on_tool_result(
        self,
        turn: int,
        *,
        tool_name: str,
        observation: str,
    ) -> None: ...

    def finalize(
        self,
        *,
        valid: bool,
        submitted: bool,
        validation_errors: list[str],
        total_latency_ms: float,
        messages: list[dict[str, Any]] | None = None,
    ) -> None: ...

    def record_failure(
        self,
        exc: Exception,
        *,
        messages: list[dict[str, Any]],
        last_response: dict[str, Any] | None = None,
    ) -> None: ...


@dataclass
class FileReactTraceRecorder:
    trace_dir: Path
    agent_name: str = "material_author"
    task_id: str | None = None
    generation_id: str | None = None
    project_id: str | None = None
    model: str | None = None
    _turns: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        storage_root: Path,
        *,
        project_id: str,
        task_id: str | None = None,
        generation_id: str | None = None,
        model: str | None = None,
    ) -> FileReactTraceRecorder:
        run_id = uuid.uuid4().hex[:12]
        trace_dir = (
            storage_root
            / "projects"
            / project_id
            / "logs"
            / "composition-author"
            / run_id
        )
        trace_dir.mkdir(parents=True, exist_ok=True)
        return cls(
            trace_dir=trace_dir,
            task_id=task_id,
            generation_id=generation_id,
            project_id=project_id,
            model=model,
        )

    def on_turn(
        self,
        turn: int,
        *,
        response: dict[str, Any],
        latency_ms: float | None = None,
    ) -> None:
        payload = {
            "turn": turn,
            "latencyMs": latency_ms,
            "response": response,
            "createdAt": _utc_now_iso(),
        }
        self._turns.append(payload)
        path = self.trace_dir / f"turn-{turn:03d}-response.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def on_tool_result(
        self,
        turn: int,
        *,
        tool_name: str,
        observation: str,
    ) -> None:
        path = self.trace_dir / f"turn-{turn:03d}-tool-{tool_name}.json"
        path.write_text(
            json.dumps(
                {
                    "turn": turn,
                    "toolName": tool_name,
                    "observation": observation,
                    "createdAt": _utc_now_iso(),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def finalize(
        self,
        *,
        valid: bool,
        submitted: bool,
        validation_errors: list[str],
        total_latency_ms: float,
        messages: list[dict[str, Any]] | None = None,
    ) -> None:
        summary = {
            "agentName": self.agent_name,
            "projectId": self.project_id,
            "taskId": self.task_id,
            "generationId": self.generation_id,
            "model": self.model,
            "outputValid": valid,
            "submitted": submitted,
            "validationErrors": validation_errors,
            "totalLatencyMs": round(total_latency_ms, 3),
            "turnCount": len(self._turns),
            "createdAt": _utc_now_iso(),
        }
        (self.trace_dir / "material-author-react-summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        if messages is not None:
            (self.trace_dir / "material-author-messages-final.json").write_text(
                json.dumps(messages, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    def record_failure(
        self,
        exc: Exception,
        *,
        messages: list[dict[str, Any]],
        last_response: dict[str, Any] | None = None,
    ) -> None:
        failure = {
            "agentName": self.agent_name,
            "projectId": self.project_id,
            "taskId": self.task_id,
            "generationId": self.generation_id,
            "message": str(exc),
            "errorType": type(exc).__name__,
            "createdAt": _utc_now_iso(),
        }
        (self.trace_dir / "material-author-failure.json").write_text(
            json.dumps(failure, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (self.trace_dir / "material-author-messages-failure.json").write_text(
            json.dumps(messages, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        if last_response is not None:
            (self.trace_dir / "material-author-last-response.json").write_text(
                json.dumps(last_response, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )


class NullReactTraceRecorder:
    trace_dir = None

    def on_turn(self, turn: int, *, response: dict[str, Any], latency_ms: float | None = None) -> None:
        return

    def on_tool_result(self, turn: int, *, tool_name: str, observation: str) -> None:
        return

    def finalize(
        self,
        *,
        valid: bool,
        submitted: bool,
        validation_errors: list[str],
        total_latency_ms: float,
        messages: list[dict[str, Any]] | None = None,
    ) -> None:
        return

    def record_failure(
        self,
        exc: Exception,
        *,
        messages: list[dict[str, Any]],
        last_response: dict[str, Any] | None = None,
    ) -> None:
        return
