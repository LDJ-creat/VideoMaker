from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field
from typing import Any

from acp.schema import (
    AllowedOutcome,
    CreateTerminalResponse,
    DeniedOutcome,
    KillTerminalResponse,
    ReadTextFileResponse,
    ReleaseTerminalResponse,
    RequestPermissionResponse,
    TerminalOutputResponse,
    WaitForTerminalExitResponse,
    WriteTextFileResponse,
)

from app.composition.acp.fs_bridge import FsBridge, PathConfinementError
from app.composition.acp.terminal_bridge import TerminalBridge, _auto_approve_enabled
from app.composition.acp.trace import AcpAuthorTraceRecorder
from app.composition.acp.trace_policy import TracePolicyMonitor
from app.observability.acp_author_recorder import AcpAuthorObservabilityContext


@dataclass
class _TerminalState:
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""


@dataclass
class HeadlessCompositionClient:
    fs_bridge: FsBridge
    trace: AcpAuthorTraceRecorder | None = None
    observability: AcpAuthorObservabilityContext | None = None
    trace_policy: TracePolicyMonitor | None = None
    terminal_bridge: TerminalBridge = field(default_factory=TerminalBridge)
    _terminals: dict[str, _TerminalState] = field(default_factory=dict)

    def on_connect(self, conn: Any) -> None:
        _ = conn

    async def request_permission(
        self,
        options: list[Any],
        session_id: str,
        tool_call: Any,
        **kwargs: Any,
    ) -> RequestPermissionResponse:
        _ = session_id, tool_call, kwargs
        if not _auto_approve_enabled():
            return RequestPermissionResponse(outcome=DeniedOutcome(outcome="cancelled"))
        option_id = options[0].option_id if options else "approve"
        if self.trace is not None:
            self.trace.record_tool_call(
                {"kind": "permission", "optionId": option_id, "autoApproved": True},
            )
        if self.observability is not None:
            self.observability.record_client_event(
                kind="permission",
                payload={"optionId": option_id, "autoApproved": True},
            )
        return RequestPermissionResponse(
            outcome=AllowedOutcome(outcome="selected", option_id=option_id),
        )

    async def session_update(self, session_id: str, update: Any, **kwargs: Any) -> None:
        _ = session_id, kwargs
        if self.trace is None and self.observability is None:
            return
        payload = update.model_dump(by_alias=True) if hasattr(update, "model_dump") else {"update": str(update)}
        if self.trace_policy is not None and isinstance(payload, dict):
            violation_path = self.trace_policy.inspect_session_update(payload)
            if violation_path and self.trace is not None:
                self.trace.record_tool_call(
                    {
                        "kind": "policy_violation",
                        "policyViolation": "read_repo_source",
                        "path": violation_path,
                        "violationCount": self.trace_policy.violation_count,
                    }
                )
        if self.trace is not None:
            self.trace.record_tool_call({"kind": "session_update", "update": payload})
        if self.observability is not None:
            self.observability.record_client_event(
                kind="session_update",
                payload={"update": payload},
            )

    async def write_text_file(
        self,
        content: str,
        path: str,
        session_id: str,
        **kwargs: Any,
    ) -> WriteTextFileResponse | None:
        _ = session_id, kwargs
        self.fs_bridge.write_text(path, content)
        return WriteTextFileResponse()

    async def read_text_file(
        self,
        path: str,
        session_id: str,
        limit: int | None = None,
        line: int | None = None,
        **kwargs: Any,
    ) -> ReadTextFileResponse:
        _ = session_id, kwargs
        text = self.fs_bridge.read_text(path)
        if line is not None:
            lines = text.splitlines()
            start = max(line - 1, 0)
            chunk = lines[start:]
            if limit is not None:
                chunk = chunk[:limit]
            text = "\n".join(chunk)
            if chunk:
                text += "\n"
        elif limit is not None:
            text = "\n".join(text.splitlines()[:limit])
            if text:
                text += "\n"
        return ReadTextFileResponse(content=text)

    async def create_terminal(
        self,
        command: str,
        session_id: str,
        args: list[str] | None = None,
        cwd: str | None = None,
        env: list[Any] | None = None,
        output_byte_limit: int | None = None,
        **kwargs: Any,
    ) -> CreateTerminalResponse:
        _ = session_id, env, output_byte_limit, kwargs
        terminal_id = uuid.uuid4().hex[:12]
        code, stdout, stderr = await self.terminal_bridge.run(
            command=command,
            args=args,
            cwd=cwd,
        )
        self._terminals[terminal_id] = _TerminalState(exit_code=code, stdout=stdout, stderr=stderr)
        if self.observability is not None:
            self.observability.record_client_event(
                kind="terminal",
                payload={"command": command, "args": args or [], "exitCode": code},
            )
        return CreateTerminalResponse(terminal_id=terminal_id)

    async def terminal_output(
        self,
        session_id: str,
        terminal_id: str,
        **kwargs: Any,
    ) -> TerminalOutputResponse:
        _ = session_id, kwargs
        state = self._terminals[terminal_id]
        return TerminalOutputResponse(output=state.stdout + state.stderr, truncated=False)

    async def release_terminal(
        self,
        session_id: str,
        terminal_id: str,
        **kwargs: Any,
    ) -> ReleaseTerminalResponse | None:
        _ = session_id, kwargs
        self._terminals.pop(terminal_id, None)
        return ReleaseTerminalResponse()

    async def wait_for_terminal_exit(
        self,
        session_id: str,
        terminal_id: str,
        **kwargs: Any,
    ) -> WaitForTerminalExitResponse:
        _ = session_id, kwargs
        state = self._terminals[terminal_id]
        return WaitForTerminalExitResponse(exit_code=int(state.exit_code or 0))

    async def kill_terminal(
        self,
        session_id: str,
        terminal_id: str,
        **kwargs: Any,
    ) -> KillTerminalResponse | None:
        _ = session_id, kwargs
        self._terminals.pop(terminal_id, None)
        return KillTerminalResponse()

    async def ext_method(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        if method == "fs/read_text_file":
            path = str(params.get("path", ""))
            try:
                content = self.fs_bridge.read_text(path)
            except PathConfinementError as exc:
                return {"error": str(exc)}
            return {"content": content}
        if method == "fs/write_text_file":
            path = str(params.get("path", ""))
            content = str(params.get("content", ""))
            try:
                self.fs_bridge.write_text(path, content)
            except PathConfinementError as exc:
                return {"error": str(exc)}
            return {}
        return {"error": f"unsupported ext_method {method}"}

    async def ext_notification(self, method: str, params: dict[str, Any]) -> None:
        if self.trace is not None:
            self.trace.record_tool_call({"kind": "ext_notification", "method": method, "params": params})
        if self.observability is not None:
            self.observability.record_client_event(
                kind="ext_notification",
                payload={"method": method, "params": params},
            )


def client_capabilities() -> dict[str, Any]:
    return {
        "fs": {"readTextFile": True, "writeTextFile": True},
        "terminal": True,
    }
