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
    assert resolve_acp_agent_command()[0] == "npx"
    assert "codex-acp" in resolve_acp_agent_command()[-1]
    assert resolve_acp_agent_label() == "codex"


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
