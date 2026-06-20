from __future__ import annotations

import json
import os
import shlex
import sys
import shutil
from pathlib import Path
from typing import Any


def _resolve_npx_executable() -> str:
    if sys.platform == "win32":
        for candidate in ("npx.cmd", "npx.exe", "npx"):
            resolved = shutil.which(candidate)
            if resolved:
                return resolved
    return "npx"


def _resolve_cursor_cli_executable() -> str:
    override = os.getenv("VIDEOMAKER_CURSOR_AGENT_BIN", "").strip()
    if override:
        return override
    local_app = os.getenv("LOCALAPPDATA", "").strip()
    if local_app:
        agent_cmd = Path(local_app) / "cursor-agent" / "agent.cmd"
        if agent_cmd.is_file():
            return str(agent_cmd)
    return "agent"


def _cursor_acp_command() -> list[str]:
    command = [_resolve_cursor_cli_executable()]
    if os.getenv("VIDEOMAKER_CURSOR_ACP_TRUST", "true").strip().lower() in {"1", "true", "yes"}:
        command.append("--trust")
    model = os.getenv("VIDEOMAKER_CURSOR_ACP_MODEL", "auto").strip()
    if model:
        command.extend(["--model", model])
    command.append("acp")
    return command


def _claude_acp_command() -> list[str]:
    return [_resolve_npx_executable(), "-y", "@agentclientprotocol/claude-agent-acp"]


def _codex_acp_command() -> list[str]:
    command = [_resolve_npx_executable(), "-y", "@zed-industries/codex-acp"]
    model = os.getenv("VIDEOMAKER_CODEX_ACP_MODEL", "").strip()
    if model:
        command.extend(["-c", f'model="{model}"'])
    return command


_SUPPORTED_AGENTS = ("claude", "codex", "cursor")


def _default_command_for_agent(agent: str) -> list[str]:
    if agent == "cursor":
        return _cursor_acp_command()
    if agent == "claude":
        return _claude_acp_command()
    if agent == "codex":
        return _codex_acp_command()
    supported = ", ".join(_SUPPORTED_AGENTS)
    raise ValueError(f"unsupported VIDEOMAKER_COMPOSITION_ACP_AGENT={agent!r}; expected one of: {supported}")


def _parse_agent_command_override() -> list[str] | None:
    override = os.getenv("VIDEOMAKER_COMPOSITION_ACP_AGENT_COMMAND", "").strip()
    if not override:
        return None
    try:
        parsed = json.loads(override)
    except json.JSONDecodeError as exc:
        raise ValueError(
            "VIDEOMAKER_COMPOSITION_ACP_AGENT_COMMAND must be a valid JSON string array"
        ) from exc
    if not isinstance(parsed, list) or not parsed:
        raise ValueError("VIDEOMAKER_COMPOSITION_ACP_AGENT_COMMAND must be a JSON string array")
    return [str(part) for part in parsed]


def resolve_acp_agent_command() -> list[str]:
    override = _parse_agent_command_override()
    if override is not None:
        return override

    agent = os.getenv("VIDEOMAKER_COMPOSITION_ACP_AGENT", "claude").strip().lower()
    return _default_command_for_agent(agent)


def resolve_acp_agent_label() -> str:
    override = _parse_agent_command_override()
    if override is not None:
        return shlex.join(override)
    return os.getenv("VIDEOMAKER_COMPOSITION_ACP_AGENT", "claude").strip().lower()


def fake_agent_command() -> list[str]:
    return [sys.executable, "-m", "app.composition.acp.fake_agent"]
