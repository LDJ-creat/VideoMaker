from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from knowledge.paths import validate_storage_segment


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


@dataclass
class AcpAuthorTraceRecorder:
    trace_dir: Path
    agent_name: str = "material_author"
    acp_agent: str = "claude"
    task_id: str | None = None
    generation_id: str | None = None
    project_id: str | None = None
    _tool_calls: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        storage_root: Path,
        *,
        project_id: str,
        acp_agent: str,
        task_id: str | None = None,
        generation_id: str | None = None,
    ) -> AcpAuthorTraceRecorder:
        validate_storage_segment(project_id, field="project_id")
        if generation_id:
            validate_storage_segment(generation_id, field="generation_id")
        run_id = uuid.uuid4().hex[:12]
        trace_dir = (
            storage_root
            / "projects"
            / project_id
            / "logs"
            / "composition-author"
            / "acp"
            / run_id
        )
        trace_dir.mkdir(parents=True, exist_ok=True)
        return cls(
            trace_dir=trace_dir,
            acp_agent=acp_agent,
            task_id=task_id,
            generation_id=generation_id,
            project_id=project_id,
        )

    @property
    def run_id(self) -> str:
        return self.trace_dir.name

    def record_session(self, payload: dict[str, Any], *, observability_run_id: str | None = None) -> None:
        merged = dict(payload)
        if observability_run_id:
            merged["observabilityRunId"] = observability_run_id
        self._write_session_json(merged)

    def record_acp_protocol_session(self, session_id: str) -> None:
        path = self.trace_dir / "session.json"
        payload: dict[str, Any] = {}
        if path.is_file():
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    payload = loaded
            except json.JSONDecodeError:
                payload = {}
        payload["acpProtocolSessionId"] = str(session_id)
        self._write_session_json(payload)

    def _write_session_json(self, payload: dict[str, Any]) -> None:
        (self.trace_dir / "session.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def record_prompt(self, *, system: str, user: str) -> None:
        (self.trace_dir / "prompt.json").write_text(
            json.dumps(
                {"system": system, "user": user, "recordedAt": _utc_now_iso()},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def record_tool_call(self, payload: dict[str, Any]) -> None:
        self._tool_calls.append(payload)
        log_path = self.trace_dir / "tool_calls.jsonl"
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def finalize(
        self,
        *,
        valid: bool,
        validation_errors: list[str],
        total_latency_ms: float,
        spec_path: str | None = None,
        repair_attempt: int = 0,
        lint_cached: bool = False,
        turn_count: int | None = None,
        hint_codes: list[str] | None = None,
        hint_code: str | None = None,
        agent_diagnostics: dict[str, Any] | None = None,
    ) -> None:
        resolved_turn = turn_count if turn_count is not None else repair_attempt + 1
        resolved_hints = list(hint_codes or [])
        if hint_code and hint_code not in resolved_hints:
            resolved_hints.append(hint_code)
        outcome: dict[str, Any] = {
            "valid": valid,
            "validationErrors": validation_errors,
            "totalLatencyMs": round(total_latency_ms, 2),
            "specPath": spec_path,
            "repairAttempt": repair_attempt,
            "finalTurn": resolved_turn,
            "turnCount": resolved_turn,
            "hintCodes": resolved_hints,
            "hintCode": resolved_hints[0] if resolved_hints else hint_code,
            "lintCached": lint_cached,
            "recordedAt": _utc_now_iso(),
            "backend": "acp",
            "acpAgent": self.acp_agent,
        }
        if agent_diagnostics:
            outcome["agentDiagnostics"] = agent_diagnostics
        (self.trace_dir / "outcome.json").write_text(
            json.dumps(outcome, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
