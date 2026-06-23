from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.observability.acp_author_recorder import (
    AcpAuthorObservabilityContext,
    resolve_acp_model_label,
)
from app.observability.sink import LocalFileSink
from app.runtime.agent_run_store import AgentRunStore


def test_resolve_acp_model_label_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VIDEOMAKER_COMPOSITION_ACP_AGENT_COMMAND", raising=False)
    monkeypatch.setenv("VIDEOMAKER_COMPOSITION_ACP_AGENT", "claude")
    monkeypatch.delenv("VIDEOMAKER_CLAUDE_ACP_MODEL", raising=False)
    assert resolve_acp_model_label() == "acp:claude"

    monkeypatch.setenv("VIDEOMAKER_COMPOSITION_ACP_AGENT", "codex")
    assert resolve_acp_model_label() == "acp:codex"

    monkeypatch.setenv("VIDEOMAKER_COMPOSITION_ACP_AGENT", "cursor")
    assert resolve_acp_model_label() == "acp:cursor"


def test_resolve_acp_model_label_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIDEOMAKER_COMPOSITION_ACP_AGENT", "claude")
    monkeypatch.setenv("VIDEOMAKER_CLAUDE_ACP_MODEL", "claude-opus-4")
    assert resolve_acp_model_label() == "claude-opus-4"


def test_record_session_start_end_writes_tool_runs(tmp_path: Path) -> None:
    sink = LocalFileSink(AgentRunStore(tmp_path))
    trace_dir = tmp_path / "trace-run-1"
    trace_dir.mkdir()
    ctx = AcpAuthorObservabilityContext.from_trace(
        sink=sink,
        trace_dir=trace_dir,
        project_id="project-1",
        task_id="task-1",
        generation_id="gen-1",
        slot_id="slot-hook",
        acp_agent="cursor",
    )

    ctx.record_session_start(
        agent_command=["agent", "acp"],
        acp_timeout_sec=600.0,
        composition_template=True,
        lint_repair_max=1,
    )
    ctx.record_lint_gate(errors=[], lint_cached=True, repair_attempt=0)
    ctx.record_session_end(valid=True, latency_ms=123.4, repair_attempt=0, lint_cached=True)

    tool_dir = tmp_path / "projects" / "project-1" / "logs" / "tool-runs"
    payloads = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in tool_dir.glob("acp-*.json")
    ]
    tool_names = {item["toolName"] for item in payloads}
    assert tool_names == {"acp_session_start", "acp_lint_gate", "acp_session_end"}

    start_payload = next(item for item in payloads if item["toolName"] == "acp_session_start")
    assert start_payload["slotId"] == "slot-hook"
    assert start_payload["metadata"]["acpTraceDir"] == str(trace_dir)

    lint_payload = next(item for item in payloads if item["toolName"] == "acp_lint_gate")
    assert lint_payload["metadata"]["lintCached"] is True

    end_payload = next(item for item in payloads if item["toolName"] == "acp_session_end")
    assert end_payload["latencyMs"] == 123.4


def test_session_update_rate_limit(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("VIDEOMAKER_ACP_OBSERVABILITY_MAX_SESSION_UPDATES", "2")
    sink = MagicMock()
    trace_dir = tmp_path / "trace-run-2"
    trace_dir.mkdir()
    ctx = AcpAuthorObservabilityContext.from_trace(
        sink=sink,
        trace_dir=trace_dir,
        project_id="project-1",
        task_id="task-1",
        generation_id=None,
        slot_id="slot-1",
        acp_agent="codex",
    )

    for index in range(3):
        ctx.record_client_event(
            kind="session_update",
            payload={"update": {"content": {"text": f"chunk-{index}"}}},
        )
    ctx.record_session_end(valid=True, latency_ms=10.0)

    assert sink.record_tool_run.call_count == 3
    end_call = sink.record_tool_run.call_args_list[-1].args[0]
    assert end_call["metadata"]["sessionUpdateDropped"] == 1


def test_session_update_truncates_large_text(tmp_path: Path) -> None:
    sink = LocalFileSink(AgentRunStore(tmp_path))
    trace_dir = tmp_path / "trace-run-3"
    trace_dir.mkdir()
    ctx = AcpAuthorObservabilityContext.from_trace(
        sink=sink,
        trace_dir=trace_dir,
        project_id="project-1",
        task_id=None,
        generation_id=None,
        slot_id="slot-1",
        acp_agent="claude",
    )
    long_text = "x" * 900
    ctx.record_client_event(
        kind="session_update",
        payload={"update": {"content": {"text": long_text}}},
    )

    tool_path = next((tmp_path / "projects" / "project-1" / "logs" / "tool-runs").glob("*.json"))
    payload = json.loads(tool_path.read_text(encoding="utf-8"))
    update = payload["input"]["update"]
    assert update["type"] == "text_ref"
    assert update["charCount"] == 900
    assert len(update["preview"]) == 512


def test_session_start_sanitizes_agent_command(tmp_path: Path) -> None:
    sink = LocalFileSink(AgentRunStore(tmp_path))
    trace_dir = tmp_path / "trace-run-4"
    trace_dir.mkdir()
    ctx = AcpAuthorObservabilityContext.from_trace(
        sink=sink,
        trace_dir=trace_dir,
        project_id="project-1",
        task_id="task-1",
        generation_id=None,
        slot_id="slot-1",
        acp_agent="cursor",
    )
    ctx.record_session_start(
        agent_command=[r"C:\Users\secret\agent.cmd", "--trust", "acp"],
        acp_timeout_sec=120.0,
        composition_template=False,
        lint_repair_max=1,
    )
    payload = json.loads(
        next((tmp_path / "projects" / "project-1" / "logs" / "tool-runs").glob("*.json")).read_text(
            encoding="utf-8"
        )
    )
    assert payload["input"]["agentCommand"]["command"] == "agent.cmd"
    assert r"C:\Users" not in json.dumps(payload["input"])


def test_session_update_summarizes_non_text_update(tmp_path: Path) -> None:
    sink = LocalFileSink(AgentRunStore(tmp_path))
    trace_dir = tmp_path / "trace-run-5"
    trace_dir.mkdir()
    ctx = AcpAuthorObservabilityContext.from_trace(
        sink=sink,
        trace_dir=trace_dir,
        project_id="project-1",
        task_id=None,
        generation_id=None,
        slot_id="slot-1",
        acp_agent="claude",
    )
    ctx.record_client_event(
        kind="session_update",
        payload={"update": {"tool": "x", "nested": {"blob": "y" * 800}}},
    )
    payload = json.loads(
        next((tmp_path / "projects" / "project-1" / "logs" / "tool-runs").glob("*.json")).read_text(
            encoding="utf-8"
        )
    )
    assert payload["input"]["update"]["type"] == "update_ref"


def test_ext_notification_sanitizes_params(tmp_path: Path) -> None:
    sink = LocalFileSink(AgentRunStore(tmp_path))
    trace_dir = tmp_path / "trace-run-6"
    trace_dir.mkdir()
    ctx = AcpAuthorObservabilityContext.from_trace(
        sink=sink,
        trace_dir=trace_dir,
        project_id="project-1",
        task_id=None,
        generation_id=None,
        slot_id="slot-1",
        acp_agent="claude",
    )
    ctx.record_client_event(
        kind="ext_notification",
        payload={
            "method": "fs/read_text_file",
            "params": {"path": r"C:\secret\material-spec.json", "token": "abc"},
        },
    )
    payload = json.loads(
        next((tmp_path / "projects" / "project-1" / "logs" / "tool-runs").glob("*.json")).read_text(
            encoding="utf-8"
        )
    )
    assert payload["input"]["method"] == "fs/read_text_file"
    assert payload["input"]["paramKeys"] == ["path", "token"]
    assert payload["input"]["pathBasename"] == "material-spec.json"
    assert "token" not in payload["input"]


def test_session_end_uses_tracked_repair_metadata(tmp_path: Path) -> None:
    sink = LocalFileSink(AgentRunStore(tmp_path))
    trace_dir = tmp_path / "trace-run-7"
    trace_dir.mkdir()
    ctx = AcpAuthorObservabilityContext.from_trace(
        sink=sink,
        trace_dir=trace_dir,
        project_id="project-1",
        task_id="task-1",
        generation_id="gen-1",
        slot_id="slot-1",
        acp_agent="codex",
    )
    ctx.record_lint_gate(errors=["lint failed"], lint_cached=False, repair_attempt=1)
    ctx.record_session_end(valid=False, latency_ms=50.0, validation_errors=["boom"])

    payloads = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in (tmp_path / "projects" / "project-1" / "logs" / "tool-runs").glob("*.json")
    ]
    end_payload = next(item for item in payloads if item["toolName"] == "acp_session_end")
    assert end_payload["metadata"]["repairAttempt"] == 1
    assert end_payload["metadata"]["lintCached"] is False


def test_langfuse_sink_acp_agent_run_metadata() -> None:
    from app.observability.langfuse_sink import LangfuseSink

    client = MagicMock()
    observation = MagicMock()
    client.create_trace_id.return_value = "a" * 32
    client.start_observation.return_value = observation
    sink = LangfuseSink(client)
    sink.record_agent_run(
        {
            "id": "run-1",
            "projectId": "project-1",
            "taskId": "task-1",
            "agentName": "material_author",
            "inputSummary": json.dumps(
                {
                    "backend": "acp",
                    "acpAgent": "cursor",
                    "slotId": "slot-1",
                    "acpTraceDir": "/tmp/trace",
                }
            ),
            "outputValid": True,
            "latencyMs": 10,
            "model": "acp:cursor",
            "promptVersion": "composition-acp-v1",
        }
    )
    kwargs = client.start_observation.call_args.kwargs
    assert kwargs["name"] == "material_author"
    assert kwargs["as_type"] == "span"
    assert kwargs["metadata"]["backend"] == "acp"
    assert kwargs["metadata"]["slotId"] == "slot-1"
    observation.end.assert_called_once()


def test_langfuse_sink_acp_tool_run_span_name() -> None:
    from app.observability.langfuse_sink import LangfuseSink

    client = MagicMock()
    observation = MagicMock()
    client.create_trace_id.return_value = "b" * 32
    client.start_observation.return_value = observation
    sink = LangfuseSink(client)
    sink.record_tool_run(
        {
            "id": "acp-run-1",
            "projectId": "project-1",
            "taskId": "task-1",
            "agentName": "material_author",
            "toolName": "acp_session_start",
            "input": {"agentCommand": {"command": "agent.cmd"}},
            "metadata": {
                "backend": "acp",
                "acpAgent": "cursor",
                "eventKind": "session_start",
            },
        }
    )
    kwargs = client.start_observation.call_args.kwargs
    assert kwargs["name"] == "material_author:acp_session_start"
    assert kwargs["as_type"] == "tool"
    assert kwargs["metadata"]["acpAgent"] == "cursor"
    assert kwargs["input"] is not None
    observation.end.assert_called_once()
