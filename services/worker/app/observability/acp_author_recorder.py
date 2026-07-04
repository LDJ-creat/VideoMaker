from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.composition.acp.agent_registry import resolve_acp_agent_label
from app.observability.capture import prepare_payload, resolve_observability_capture
from app.observability.sink import ObservabilitySink

logger = logging.getLogger(__name__)

_SESSION_UPDATE_PREVIEW_CHARS = 512


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _acp_max_session_updates() -> int:
    raw = os.getenv("VIDEOMAKER_ACP_OBSERVABILITY_MAX_SESSION_UPDATES", "40").strip()
    try:
        return max(0, int(raw))
    except ValueError:
        return 40


def resolve_acp_model_label() -> str:
    agent = resolve_acp_agent_label().strip().lower()
    if agent == "claude":
        model = os.getenv("VIDEOMAKER_CLAUDE_ACP_MODEL", "").strip()
        return model or "acp:claude"
    if agent == "codex":
        model = os.getenv("VIDEOMAKER_CODEX_ACP_MODEL", "").strip()
        return model or "acp:codex"
    if agent == "cursor":
        model = os.getenv("VIDEOMAKER_CURSOR_ACP_MODEL", "").strip()
        return model or "acp:cursor"
    return f"acp:{agent}"


@dataclass
class AcpAuthorObservabilityContext:
    sink: ObservabilitySink
    project_id: str
    task_id: str | None
    generation_id: str | None
    slot_id: str
    run_id: str
    acp_agent: str
    acp_trace_dir: str
    capture: str = field(default_factory=resolve_observability_capture)
    _event_seq: int = field(default=0, repr=False)
    _session_update_count: int = field(default=0, repr=False)
    _session_update_dropped: int = field(default=0, repr=False)
    _last_repair_attempt: int = field(default=0, repr=False)
    _last_lint_cached: bool = field(default=False, repr=False)

    @classmethod
    def from_trace(
        cls,
        *,
        sink: ObservabilitySink,
        trace_dir: Path,
        project_id: str,
        task_id: str | None,
        generation_id: str | None,
        slot_id: str,
        acp_agent: str,
    ) -> AcpAuthorObservabilityContext:
        return cls(
            sink=sink,
            project_id=project_id,
            task_id=task_id,
            generation_id=generation_id,
            slot_id=slot_id,
            run_id=trace_dir.name,
            acp_agent=acp_agent,
            acp_trace_dir=str(trace_dir),
        )

    def note_session_progress(self, *, repair_attempt: int, lint_cached: bool) -> None:
        self._last_repair_attempt = repair_attempt
        self._last_lint_cached = lint_cached

    def _emit_tool_run(
        self,
        *,
        tool_name: str,
        event_kind: str,
        latency_ms: float = 0.0,
        input_payload: Any = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self._event_seq += 1
        merged_metadata: dict[str, Any] = {
            "backend": "acp",
            "acpAgent": self.acp_agent,
            "acpTraceDir": self.acp_trace_dir,
            "eventKind": event_kind,
        }
        if metadata:
            merged_metadata.update(metadata)

        payload: dict[str, Any] = {
            "id": f"acp-{self.run_id}-{event_kind}-{self._event_seq}",
            "projectId": self.project_id,
            "agentName": "material_author",
            "toolName": tool_name,
            "latencyMs": round(latency_ms, 3),
            "createdAt": _utc_now_iso(),
            "slotId": self.slot_id,
            "metadata": merged_metadata,
        }
        if self.task_id:
            payload["taskId"] = self.task_id
        if self.generation_id:
            payload["generationId"] = self.generation_id
        if input_payload is not None:
            payload["input"] = prepare_payload(input_payload, capture=self.capture)

        try:
            self.sink.record_tool_run(payload)
        except Exception:
            logger.exception("AcpAuthorObservabilityContext failed to record %s", tool_name)

    def record_session_start(
        self,
        *,
        agent_command: list[str],
        acp_timeout_sec: float,
        composition_template: bool,
        lint_repair_max: int,
        max_turns: int | None = None,
        prompt_timeout_sec: float | None = None,
        in_session_review_enabled: bool | None = None,
    ) -> None:
        self._emit_tool_run(
            tool_name="acp_session_start",
            event_kind="session_start",
            input_payload={
                "agentCommand": _sanitize_agent_command(agent_command),
                "acpTimeoutSec": acp_timeout_sec,
                "promptTimeoutSec": prompt_timeout_sec,
                "compositionTemplate": composition_template,
                "lintRepairMax": lint_repair_max,
                "maxTurns": max_turns or lint_repair_max + 1,
                "inSessionReviewEnabled": in_session_review_enabled,
            },
        )

    def record_turn_start(self, *, turn: int) -> None:
        self._emit_tool_run(
            tool_name="acp_turn_start",
            event_kind="turn_start",
            input_payload={"turn": turn},
            metadata={"turn": turn},
        )

    def record_turn_followup(self, *, turn: int, errors: list[str] | None = None) -> None:
        self.note_session_progress(repair_attempt=turn, lint_cached=self._last_lint_cached)
        self._emit_tool_run(
            tool_name="acp_turn_followup",
            event_kind="turn_followup",
            input_payload={
                "turn": turn,
                "errors": "; ".join(errors or [])[:500],
            },
            metadata={"turn": turn, "repairAttempt": turn},
        )

    def record_turn_lint_gate(
        self,
        *,
        turn: int,
        errors: list[str],
        lint_cached: bool,
        latency_ms: float = 0.0,
    ) -> None:
        self.note_session_progress(repair_attempt=max(0, turn - 1), lint_cached=lint_cached)
        self._emit_tool_run(
            tool_name="acp_turn_lint_gate",
            event_kind="turn_lint_gate",
            latency_ms=latency_ms,
            input_payload={
                "turn": turn,
                "errors": errors[:20],
                "lintCached": lint_cached,
            },
            metadata={
                "turn": turn,
                "lintCached": lint_cached,
                "repairAttempt": max(0, turn - 1),
                "outputValid": not errors,
            },
        )

    def record_turn_review_gate(
        self,
        *,
        turn: int,
        errors: list[str],
        hard_gate_failed: bool,
        approved: bool,
        latency_ms: float = 0.0,
    ) -> None:
        self._emit_tool_run(
            tool_name="acp_turn_review_gate",
            event_kind="turn_review_gate",
            latency_ms=latency_ms,
            input_payload={
                "turn": turn,
                "errors": errors[:20],
                "hardGateFailed": hard_gate_failed,
                "approved": approved,
            },
            metadata={
                "turn": turn,
                "hardGateFailed": hard_gate_failed,
                "approved": approved,
                "repairAttempt": max(0, turn - 1),
                "outputValid": not errors,
            },
        )

    def record_session_retry(
        self,
        *,
        attempt: int,
        error: str,
        agent_diagnostics: dict[str, Any] | None = None,
    ) -> None:
        input_payload: dict[str, Any] = {"attempt": attempt, "error": error[:500]}
        if agent_diagnostics:
            input_payload["agentDiagnostics"] = agent_diagnostics
        self._emit_tool_run(
            tool_name="acp_session_retry",
            event_kind="session_retry",
            input_payload=input_payload,
            metadata={"sessionRetryAttempt": attempt},
        )

    def record_session_end(
        self,
        *,
        valid: bool,
        latency_ms: float,
        repair_attempt: int | None = None,
        lint_cached: bool | None = None,
        validation_errors: list[str] | None = None,
        turn_count: int | None = None,
        hint_codes: list[str] | None = None,
        agent_diagnostics: dict[str, Any] | None = None,
    ) -> None:
        resolved_repair = self._last_repair_attempt if repair_attempt is None else repair_attempt
        resolved_lint_cached = self._last_lint_cached if lint_cached is None else lint_cached
        resolved_turn = turn_count if turn_count is not None else resolved_repair + 1
        metadata: dict[str, Any] = {
            "outputValid": valid,
            "repairAttempt": resolved_repair,
            "turnCount": resolved_turn,
            "lintCached": resolved_lint_cached,
        }
        if hint_codes:
            metadata["hintCodes"] = hint_codes[:10]
        if self._session_update_dropped:
            metadata["sessionUpdateDropped"] = self._session_update_dropped
        self._emit_tool_run(
            tool_name="acp_session_end",
            event_kind="session_end",
            latency_ms=latency_ms,
            input_payload={
                "valid": valid,
                "validationErrors": (validation_errors or [])[:10],
                **({"agentDiagnostics": agent_diagnostics} if agent_diagnostics else {}),
            },
            metadata=metadata,
        )

    def record_repair_attempt(self, *, attempt: int, errors: list[str] | None = None) -> None:
        self.note_session_progress(repair_attempt=attempt, lint_cached=self._last_lint_cached)
        self._emit_tool_run(
            tool_name="acp_repair",
            event_kind="repair",
            input_payload={
                "attempt": attempt,
                "errors": "; ".join(errors or [])[:500],
            },
            metadata={"repairAttempt": attempt},
        )

    def record_lint_gate(
        self,
        *,
        errors: list[str],
        lint_cached: bool,
        latency_ms: float = 0.0,
        repair_attempt: int = 0,
    ) -> None:
        self.note_session_progress(repair_attempt=repair_attempt, lint_cached=lint_cached)
        self._emit_tool_run(
            tool_name="acp_lint_gate",
            event_kind="lint_gate",
            latency_ms=latency_ms,
            input_payload={
                "errors": errors[:20],
                "lintCached": lint_cached,
            },
            metadata={
                "lintCached": lint_cached,
                "repairAttempt": repair_attempt,
                "outputValid": not errors,
            },
        )

    def record_client_event(self, *, kind: str, payload: dict[str, Any] | None = None) -> None:
        if kind == "session_update":
            limit = _acp_max_session_updates()
            if self._session_update_count >= limit:
                self._session_update_dropped += 1
                return
            self._session_update_count += 1
            sanitized = _sanitize_session_update(payload or {})
        elif kind == "terminal":
            sanitized = _sanitize_terminal_payload(payload or {})
        elif kind == "ext_notification":
            sanitized = _sanitize_ext_notification_payload(payload or {})
        else:
            sanitized = prepare_payload(payload or {}, capture=self.capture)

        tool_name = f"acp_{kind}"
        self._emit_tool_run(
            tool_name=tool_name,
            event_kind=kind,
            input_payload=sanitized,
        )


def _sanitize_agent_command(command: list[str]) -> dict[str, Any]:
    if not command:
        return {"command": "", "argsPreview": ""}
    return {
        "command": Path(str(command[0])).name or str(command[0]),
        "argsPreview": " ".join(str(item) for item in command[1:])[:200],
    }


def _sanitize_session_update(payload: dict[str, Any]) -> dict[str, Any]:
    cloned = dict(payload)
    update = cloned.get("update")
    if not isinstance(update, dict):
        return _summarize_unknown_payload(cloned)

    text = _extract_update_text(update)
    if text:
        if len(text) > _SESSION_UPDATE_PREVIEW_CHARS:
            cloned["update"] = {
                "type": "text_ref",
                "preview": text[:_SESSION_UPDATE_PREVIEW_CHARS],
                "charCount": len(text),
            }
        else:
            cloned["update"] = update
        return cloned

    serialized = json.dumps(update, ensure_ascii=False)
    if len(serialized) <= _SESSION_UPDATE_PREVIEW_CHARS:
        cloned["update"] = update
    else:
        cloned["update"] = {
            "type": "update_ref",
            "charCount": len(serialized),
            "sha256Prefix": hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16],
            "preview": serialized[:_SESSION_UPDATE_PREVIEW_CHARS],
        }
    return cloned


def _summarize_unknown_payload(payload: dict[str, Any]) -> dict[str, Any]:
    serialized = json.dumps(payload, ensure_ascii=False)
    if len(serialized) <= _SESSION_UPDATE_PREVIEW_CHARS:
        return payload
    return {
        "type": "payload_ref",
        "charCount": len(serialized),
        "sha256Prefix": hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16],
        "preview": serialized[:_SESSION_UPDATE_PREVIEW_CHARS],
    }


def _extract_update_text(update: dict[str, Any]) -> str:
    content = update.get("content")
    if isinstance(content, dict):
        return str(content.get("text", "")).strip()
    if isinstance(content, str):
        return content.strip()
    return ""


def _sanitize_terminal_payload(payload: dict[str, Any]) -> dict[str, Any]:
    command = str(payload.get("command", ""))
    args = payload.get("args")
    arg_text = " ".join(str(item) for item in args) if isinstance(args, list) else ""
    sanitized: dict[str, Any] = {
        "command": Path(command).name or command,
        "argsPreview": arg_text[:200],
    }
    if "exitCode" in payload:
        sanitized["exitCode"] = payload.get("exitCode")
    return sanitized


def _sanitize_ext_notification_payload(payload: dict[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    if "method" in payload:
        sanitized["method"] = payload["method"]
    params = payload.get("params")
    if isinstance(params, dict):
        sanitized["paramKeys"] = sorted(str(key) for key in params.keys())
        path = params.get("path")
        if isinstance(path, str):
            sanitized["pathBasename"] = Path(path).name
    return sanitized
