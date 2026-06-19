from __future__ import annotations

import json
import os
import shlex
import sys
from typing import Any


_DEFAULT_COMMANDS: dict[str, list[str]] = {
    "claude": ["npx", "-y", "@agentclientprotocol/claude-agent-acp"],
    "codex": ["npx", "-y", "@zed-industries/codex-acp"],
    "cursor": ["cursor", "--acp"],
}


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
    command = _DEFAULT_COMMANDS.get(agent)
    if command is None:
        supported = ", ".join(sorted(_DEFAULT_COMMANDS))
        raise ValueError(f"unsupported VIDEOMAKER_COMPOSITION_ACP_AGENT={agent!r}; expected one of: {supported}")
    return list(command)


def resolve_acp_agent_label() -> str:
    override = _parse_agent_command_override()
    if override is not None:
        return shlex.join(override)
    return os.getenv("VIDEOMAKER_COMPOSITION_ACP_AGENT", "claude").strip().lower()


def fake_agent_command() -> list[str]:
    return [sys.executable, "-m", "app.composition.acp.fake_agent"]
