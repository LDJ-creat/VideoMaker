from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.gateway.config import GatewayConfig
from app.gateway.model_gateway import ModelGateway
from app.gateway.providers.base import ProviderConfig
from app.observability.sink import LocalFileSink, MultiSink, build_observability_sink
from app.runtime.agent_run_store import AgentRunLog, AgentRunStore
from app.runtime.model_call_store import ModelCallStore


def _gateway_config() -> GatewayConfig:
    cfg = ProviderConfig(base_url="https://api.example.com/v1", api_key="sk-test", model="gpt-test")
    return GatewayConfig(
        text=cfg,
        vision=cfg,
        video_understanding=cfg,
        tts=cfg,
        image=cfg,
        video_driver="generic_job",
        video=cfg,
    )


def test_local_file_sink_records_model_call(tmp_path: Path) -> None:
    sink = LocalFileSink(AgentRunStore(tmp_path), ModelCallStore(tmp_path))
    sink.record_model_call(
        {
            "projectId": "project-1",
            "id": "call-1",
            "callKind": "chat_json",
            "profile": "text",
            "model": "gpt-test",
            "driver": "openai_compatible",
            "outputValid": True,
            "latencyMs": 12.5,
            "createdAt": "2026-06-19T12:00:00Z",
            "input": {"messages": []},
            "output": {"ok": True},
        }
    )

    log_path = tmp_path / "projects" / "project-1" / "logs" / "model-calls" / "call-1.json"
    payload = json.loads(log_path.read_text(encoding="utf-8"))
    assert payload["callKind"] == "chat_json"
    assert payload["outputValid"] is True


def test_multi_sink_records_model_call_and_flushes() -> None:
    first = MagicMock()
    second = MagicMock()
    sink = MultiSink([first, second])
    payload = {"id": "call-1", "callKind": "tts"}

    sink.record_model_call(payload)
    sink.flush()

    first.record_model_call.assert_called_once_with(payload)
    second.record_model_call.assert_called_once_with(payload)
    first.flush.assert_called_once()
    second.flush.assert_called_once()


def test_build_observability_sink_skips_langfuse_when_disabled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LANGFUSE_ENABLED", raising=False)
    sink = build_observability_sink(tmp_path)
    assert hasattr(sink, "record_model_call")
    assert hasattr(sink, "flush")


def test_model_gateway_records_chat_call(tmp_path: Path) -> None:
    store = AgentRunStore(tmp_path)
    sink = LocalFileSink(store, ModelCallStore(tmp_path))
    gateway = ModelGateway(config=_gateway_config())
    gateway.observability = type(
        "Ctx",
        (),
        {
            "sink": sink,
            "project_id": "project-1",
            "task_id": "task-1",
            "generation_id": None,
            "agent_name": "slot_mapper",
            "slot_id": None,
            "turn": None,
            "effective_capture": "full",
        },
    )()

    provider = MagicMock()
    provider.config = _gateway_config().text
    provider.last_latency_ms = 42
    provider.last_token_usage = {"prompt": 3, "completion": 5}
    provider.complete.return_value = '{"slotId":"hook"}'
    gateway._chat_providers["text"] = provider

    result = gateway.complete_json("map slots", {"inputs": {}}, "gap-report", profile="text")
    assert result["slotId"] == "hook"

    log_dir = tmp_path / "projects" / "project-1" / "logs" / "model-calls"
    files = list(log_dir.glob("*.json"))
    assert len(files) == 1
    payload = json.loads(files[0].read_text(encoding="utf-8"))
    assert payload["callKind"] == "chat_json"
    assert payload["agentName"] == "slot_mapper"
    assert payload["tokenUsage"] == {"prompt": 3, "completion": 5}


def test_capture_summary_strips_large_base64(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.observability.capture import prepare_payload

    monkeypatch.setenv("VIDEOMAKER_OBSERVABILITY_CAPTURE", "summary")
    value = prepare_payload(
        {"url": "data:image/png;base64," + ("A" * 5000)},
        capture="summary",
    )
    assert isinstance(value, dict)
    assert value["url"]["type"] == "data_url_ref"


def test_capture_full_redacts_sensitive_fields() -> None:
    from app.observability.capture import prepare_payload

    long_text = "narration " * 50
    payload = prepare_payload(
        {
            "text": long_text,
            "path": "/storage/projects/p1/samples/s1/keyframes/frame-001.jpg",
            "imageBase64": "A" * 4000,
        },
        capture="full",
    )
    assert payload["text"]["type"] == "text_ref"
    assert payload["path"]["type"] == "path_ref"
    assert payload["imageBase64"]["type"] == "base64_ref"


def test_local_file_sink_amend_model_call(tmp_path: Path) -> None:
    store = AgentRunStore(tmp_path)
    model_store = ModelCallStore(tmp_path)
    sink = LocalFileSink(store, model_store)
    sink.record_model_call(
        {
            "projectId": "project-1",
            "id": "call-amend",
            "callKind": "chat_json",
            "profile": "text",
            "model": "gpt-test",
            "driver": "openai_compatible",
            "outputValid": True,
            "latencyMs": 10,
            "createdAt": "2026-06-19T12:00:00Z",
        }
    )
    sink.amend_model_call(
        {
            "projectId": "project-1",
            "id": "call-amend",
            "outputValid": False,
            "error": {
                "code": "post_validation_failed",
                "message": "schema mismatch",
                "retryable": True,
            },
        }
    )
    payload = json.loads(
        (tmp_path / "projects" / "project-1" / "logs" / "model-calls" / "call-amend.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["outputValid"] is False
    assert payload["error"]["code"] == "post_validation_failed"


def test_invalidate_last_model_call_updates_local_log(tmp_path: Path) -> None:
    from app.observability.gateway_context import GatewayObservability
    from app.observability.model_call_recorder import invalidate_last_model_call, record_model_call

    store = AgentRunStore(tmp_path)
    sink = LocalFileSink(store, ModelCallStore(tmp_path))
    gateway = ModelGateway(config=_gateway_config())
    gateway.observability = GatewayObservability(
        sink=sink,
        project_id="project-1",
        task_id="task-1",
    )

    call_id = record_model_call(
        gateway,
        call_kind="chat_json",
        profile="text",
        model="gpt-test",
        driver="openai_compatible",
        input_payload={"messages": []},
        started=0,
        output_payload={"ok": True},
        output_valid=True,
    )
    assert call_id is not None
    invalidate_last_model_call(gateway, validation_errors=["bad schema"])

    payload = json.loads(
        (tmp_path / "projects" / "project-1" / "logs" / "model-calls" / f"{call_id}.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["outputValid"] is False
    assert payload["error"]["code"] == "post_validation_failed"


def test_agent_observability_scope_restores_agent_name() -> None:
    from app.observability.gateway_context import GatewayObservability, agent_observability_scope

    gateway = ModelGateway(config=_gateway_config())
    gateway.observability = GatewayObservability(
        sink=MagicMock(),
        project_id="project-1",
        agent_name="structure_analyst",
    )
    with agent_observability_scope(gateway, "segment_analyst"):
        assert gateway.observability.agent_name == "segment_analyst"
    assert gateway.observability.agent_name == "structure_analyst"


def test_complete_text_records_chat_text_kind(tmp_path: Path) -> None:
    store = AgentRunStore(tmp_path)
    sink = LocalFileSink(store, ModelCallStore(tmp_path))
    gateway = ModelGateway(config=_gateway_config())
    gateway.observability = type(
        "Ctx",
        (),
        {
            "sink": sink,
            "project_id": "project-1",
            "task_id": "task-1",
            "generation_id": None,
            "agent_name": None,
            "slot_id": None,
            "turn": None,
            "effective_capture": "full",
            "last_model_call_id": None,
        },
    )()

    provider = MagicMock()
    provider.config = _gateway_config().text
    provider.last_latency_ms = 12
    provider.last_token_usage = {"prompt": 1, "completion": 2}
    provider.complete.return_value = "plain text"
    gateway._chat_providers["text"] = provider

    assert gateway.complete_text("hello", {"inputs": {}}) == "plain text"

    log_dir = tmp_path / "projects" / "project-1" / "logs" / "model-calls"
    payload = json.loads(next(log_dir.glob("*.json")).read_text(encoding="utf-8"))
    assert payload["callKind"] == "chat_text"
