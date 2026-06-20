from __future__ import annotations

import json
import os

import pytest

from app.composition.acp.agent_registry import (
    fake_agent_command,
    resolve_acp_agent_command,
    resolve_acp_agent_label,
)


def test_resolve_acp_agent_command_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VIDEOMAKER_COMPOSITION_ACP_AGENT_COMMAND", raising=False)
    monkeypatch.setenv("VIDEOMAKER_COMPOSITION_ACP_AGENT", "codex")
    command = resolve_acp_agent_command()
    assert command[0].endswith("npx") or command[0].endswith("npx.cmd")
    assert "codex-acp" in command[-1]
    assert resolve_acp_agent_label() == "codex"


def test_resolve_codex_acp_command_with_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VIDEOMAKER_COMPOSITION_ACP_AGENT_COMMAND", raising=False)
    monkeypatch.setenv("VIDEOMAKER_COMPOSITION_ACP_AGENT", "codex")
    monkeypatch.setenv("VIDEOMAKER_CODEX_ACP_MODEL", "gpt-5.2")
    command = resolve_acp_agent_command()
    assert command[0].endswith("npx") or command[0].endswith("npx.cmd")
    assert command[1:] == [
        "-y",
        "@zed-industries/codex-acp",
        "-c",
        'model="gpt-5.2"',
    ]


def test_resolve_cursor_acp_command(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VIDEOMAKER_COMPOSITION_ACP_AGENT_COMMAND", raising=False)
    monkeypatch.setenv("VIDEOMAKER_COMPOSITION_ACP_AGENT", "cursor")
    monkeypatch.setenv("VIDEOMAKER_CURSOR_AGENT_BIN", r"C:\fake\agent.cmd")
    monkeypatch.setenv("VIDEOMAKER_CURSOR_ACP_MODEL", "auto")
    assert resolve_acp_agent_command() == [r"C:\fake\agent.cmd", "--trust", "--model", "auto", "acp"]
    assert resolve_acp_agent_label() == "cursor"


def test_resolve_acp_agent_command_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIDEOMAKER_COMPOSITION_ACP_AGENT_COMMAND", json.dumps(["cursor", "--acp"]))
    assert resolve_acp_agent_command() == ["cursor", "--acp"]


def test_fake_agent_command_uses_python_module() -> None:
    command = fake_agent_command()
    assert command[0]
    assert command[-1] == "app.composition.acp.fake_agent"


def test_unknown_agent_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VIDEOMAKER_COMPOSITION_ACP_AGENT_COMMAND", raising=False)
    monkeypatch.setenv("VIDEOMAKER_COMPOSITION_ACP_AGENT", "unknown-agent")
    with pytest.raises(ValueError, match="unsupported"):
        resolve_acp_agent_command()


def test_malformed_agent_command_override_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIDEOMAKER_COMPOSITION_ACP_AGENT_COMMAND", "not-json")
    with pytest.raises(ValueError, match="valid JSON"):
        resolve_acp_agent_command()
