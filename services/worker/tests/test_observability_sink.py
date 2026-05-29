from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.observability.sink import (
    LocalFileSink,
    MultiSink,
    build_observability_sink,
)
from app.runtime.agent_run_store import AgentRunLog, AgentRunStore


def test_local_file_sink_records_agent_run(tmp_path: Path) -> None:
    sink = LocalFileSink(AgentRunStore(tmp_path))
    sink.record_agent_run(
        {
            "projectId": "project-1",
            "id": "run-1",
            "agentName": "structure_analyst",
            "promptVersion": "abc12345",
            "model": "fixture",
            "task": "structure_analyst",
            "inputSummary": "{}",
            "outputValid": True,
            "latencyMs": 12.5,
            "createdAt": "2026-05-29T12:00:00Z",
        }
    )

    log_path = (
        tmp_path
        / "projects"
        / "project-1"
        / "logs"
        / "agent-runs"
        / "run-1.json"
    )
    payload = json.loads(log_path.read_text(encoding="utf-8"))
    assert payload["agentName"] == "structure_analyst"
    assert payload["outputValid"] is True


def test_local_file_sink_records_tool_run(tmp_path: Path) -> None:
    sink = LocalFileSink(AgentRunStore(tmp_path))
    sink.record_tool_run(
        {
            "projectId": "project-1",
            "id": "tool-1",
            "toolName": "ffmpeg",
            "latencyMs": 42,
        }
    )

    tool_path = (
        tmp_path
        / "projects"
        / "project-1"
        / "logs"
        / "tool-runs"
        / "tool-1.json"
    )
    payload = json.loads(tool_path.read_text(encoding="utf-8"))
    assert payload["toolName"] == "ffmpeg"


def test_multi_sink_fans_out_to_all_sinks() -> None:
    first = MagicMock()
    second = MagicMock()
    sink = MultiSink([first, second])
    payload = {"id": "run-1", "agentName": "slot_mapper"}

    sink.record_agent_run(payload)
    sink.record_tool_run(payload)

    first.record_agent_run.assert_called_once_with(payload)
    second.record_agent_run.assert_called_once_with(payload)
    first.record_tool_run.assert_called_once_with(payload)
    second.record_tool_run.assert_called_once_with(payload)


def test_multi_sink_swallows_sink_failures() -> None:
    failing = MagicMock()
    failing.record_agent_run.side_effect = RuntimeError("langfuse down")
    succeeding = MagicMock()
    sink = MultiSink([succeeding, failing])
    payload = {
        "projectId": "project-1",
        "id": "run-1",
        "agentName": "slot_mapper",
        "promptVersion": "abc12345",
        "model": "fixture",
        "task": "slot_mapper",
        "inputSummary": "{}",
        "outputValid": True,
        "latencyMs": 1.0,
        "createdAt": "2026-05-29T12:00:00Z",
    }

    sink.record_agent_run(payload)

    succeeding.record_agent_run.assert_called_once_with(payload)
    failing.record_agent_run.assert_called_once_with(payload)


def test_build_observability_sink_defaults_to_local_file(tmp_path: Path) -> None:
    sink = build_observability_sink(tmp_path)
    sink.record_agent_run(
        {
            "projectId": "project-1",
            "id": "run-default",
            "agentName": "gap_planner",
            "promptVersion": "abc12345",
            "model": "fixture",
            "task": "gap_planner",
            "inputSummary": "{}",
            "outputValid": True,
            "latencyMs": 1.0,
            "createdAt": "2026-05-29T12:00:00Z",
        }
    )

    log_path = (
        tmp_path
        / "projects"
        / "project-1"
        / "logs"
        / "agent-runs"
        / "run-default.json"
    )
    assert log_path.is_file()


def test_build_observability_sink_skips_langfuse_when_disabled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LANGFUSE_ENABLED", raising=False)
    sink = build_observability_sink(tmp_path)
    assert not isinstance(sink, MultiSink)


def test_build_observability_sink_skips_langfuse_without_sdk(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LANGFUSE_ENABLED", "true")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test")
    sink = build_observability_sink(tmp_path)
    assert not isinstance(sink, MultiSink)


def test_local_file_sink_requires_project_id(tmp_path: Path) -> None:
    sink = LocalFileSink(AgentRunStore(tmp_path))
    with pytest.raises(ValueError, match="projectId"):
        sink.record_agent_run(
            AgentRunLog(
                agent_name="structure_analyst",
                prompt_version="abc12345",
                model="fixture",
                task="structure_analyst",
                input_summary="{}",
                output_valid=True,
                latency_ms=1.0,
            ).to_payload()
        )
