from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.agents.runner import AgentRunner
from app.agents.prompt_loader import PromptLoader
from app.gateway.config import GatewayConfig
from app.gateway.model_gateway import ModelGateway
from app.gateway.providers.base import ProviderConfig
from app.observability.material_review_recorder import (
    record_material_review_tool_run,
    record_material_reviewer_agent_run,
    setup_material_review_observability,
)
from app.observability.sink import LocalFileSink
from app.pipelines.material_review import run_slot_review
from app.runtime.agent_run_store import AgentRunStore
from app.runtime.model_call_store import ModelCallStore
from app.runtime.task_context import TaskContext
from app.tools.llm_tool import LLMTool


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


def test_setup_material_review_observability_sets_slot_id(tmp_path: Path) -> None:
    sink = LocalFileSink(AgentRunStore(tmp_path), ModelCallStore(tmp_path))
    gateway = ModelGateway(config=_gateway_config())
    _, resolved_sink = setup_material_review_observability(
        storage_root=tmp_path,
        project_id="project-1",
        task_id="task-1",
        generation_id="gen-1",
        slot_id="hook",
        gateway=gateway,
        sink=sink,
    )
    assert resolved_sink is sink
    assert gateway.observability is not None
    assert gateway.observability.slot_id == "hook"
    assert gateway.observability.agent_name == "material_reviewer"


def test_record_material_reviewer_agent_run_writes_log(tmp_path: Path) -> None:
    sink = LocalFileSink(AgentRunStore(tmp_path), ModelCallStore(tmp_path))
    run_id = record_material_reviewer_agent_run(
        sink=sink,
        project_id="project-1",
        task_id="task-1",
        generation_id="gen-1",
        route="video",
        slot_id="hook",
        agent_review_round=1,
        payload_keys=["slotId", "materialSpec"],
        output_valid=True,
        latency_ms=15.0,
        model="gpt-test",
    )
    log_path = tmp_path / "projects" / "project-1" / "logs" / "agent-runs" / f"{run_id}.json"
    payload = json.loads(log_path.read_text(encoding="utf-8"))
    assert payload["agentName"] == "material_reviewer"
    assert payload["generationId"] == "gen-1"


def test_record_material_reviewer_agent_run_strips_token_usage_total(tmp_path: Path) -> None:
    sink = LocalFileSink(AgentRunStore(tmp_path), ModelCallStore(tmp_path))
    run_id = record_material_reviewer_agent_run(
        sink=sink,
        project_id="project-1",
        task_id="task-1",
        generation_id="gen-1",
        route="video",
        slot_id="hook",
        agent_review_round=1,
        payload_keys=["slotId"],
        output_valid=True,
        latency_ms=12.0,
        model="gpt-test",
        token_usage={"prompt": 100, "completion": 50, "total": 150},
    )
    log_path = tmp_path / "projects" / "project-1" / "logs" / "agent-runs" / f"{run_id}.json"
    payload = json.loads(log_path.read_text(encoding="utf-8"))
    assert payload["tokenUsage"] == {"prompt": 100.0, "completion": 50.0}


def test_record_material_reviewer_agent_run_skips_invalid_agent_run_log(tmp_path: Path) -> None:
    class FailingSink(LocalFileSink):
        def record_agent_run(self, log: dict) -> None:
            raise ValueError(
                "Invalid AgentRunLog payload: "
                "[ValidationErrorItem(path='$.tokenUsage', message=\"Additional properties are not allowed ('total' was unexpected)\", validator='additionalProperties')]"
            )

    sink = FailingSink(AgentRunStore(tmp_path), ModelCallStore(tmp_path))
    run_id = record_material_reviewer_agent_run(
        sink=sink,
        project_id="project-1",
        task_id="task-1",
        generation_id="gen-1",
        route="video",
        slot_id="hook",
        agent_review_round=1,
        payload_keys=["slotId"],
        output_valid=True,
        latency_ms=12.0,
        model="gpt-test",
        token_usage={"prompt": 100, "completion": 50, "total": 150},
    )
    assert run_id
    log_dir = tmp_path / "projects" / "project-1" / "logs" / "agent-runs"
    assert not any(log_dir.glob("*.json")) if log_dir.exists() else True


def test_run_slot_review_persists_trace_and_model_call(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    generation_root = tmp_path / "projects" / "project-1" / "generations" / "gen-1"
    generation_root.mkdir(parents=True)
    preview = generation_root / "preview.mp4"
    preview.write_bytes(b"\x00" * 2048)

    sink = LocalFileSink(AgentRunStore(tmp_path), ModelCallStore(tmp_path))
    gateway = ModelGateway(config=_gateway_config())
    setup_material_review_observability(
        storage_root=tmp_path,
        project_id="project-1",
        task_id="task-1",
        generation_id="gen-1",
        slot_id="hook",
        gateway=gateway,
        sink=sink,
    )

    class FakeFFmpeg:
        def probe(self, _path: Path) -> dict:
            return {"durationSec": 3.0}

    monkeypatch.setattr("app.pipelines.material_review.FFmpegTool", FakeFFmpeg)
    monkeypatch.setattr(
        "app.pipelines.material_review.resolve_material_review_route",
        lambda **_: "video",
    )
    monkeypatch.setattr(
        ModelGateway,
        "build_video_structure_messages",
        staticmethod(lambda **_: [{"role": "user", "content": "review"}]),
    )

    provider = MagicMock()
    provider.config = _gateway_config().video_understanding
    provider.last_latency_ms = 20.0
    provider.last_token_usage = {"prompt": 10, "completion": 4}
    provider.complete.return_value = json.dumps(
        {"approved": True, "issues": [], "suggestions": []},
    )
    gateway._chat_providers["video_understanding"] = provider

    context = TaskContext(
        task_id="task-1",
        project_id="project-1",
        storage_root=tmp_path,
    )
    spec = {"template": "composition", "durationSec": 3.0}
    report = run_slot_review(
        runner=None,
        context=context,
        gateway=gateway,
        store=None,
        preview_path=preview,
        spec=spec,
        author_payload={"projectId": "project-1", "taskId": "task-1", "slotTiming": {"durationSec": 3.0}},
        slot_id="hook",
        generation_id="gen-1",
        generation_root=generation_root,
        observability_sink=sink,
    )

    assert report["trace"]["reviewRoute"] == "video"
    assert report["trace"].get("agentRunId")
    model_calls = list((tmp_path / "projects" / "project-1" / "logs" / "model-calls").glob("*.json"))
    assert len(model_calls) == 1
    model_payload = json.loads(model_calls[0].read_text(encoding="utf-8"))
    assert model_payload["agentName"] == "material_reviewer"
    assert model_payload["slotId"] == "hook"


def test_hard_gate_report_has_trace_without_model_call(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    missing = tmp_path / "missing.mp4"
    sink = LocalFileSink(AgentRunStore(tmp_path), ModelCallStore(tmp_path))
    report = run_slot_review(
        runner=None,
        context=None,
        gateway=None,
        store=None,
        preview_path=missing,
        spec={"durationSec": 3.0},
        author_payload={},
        slot_id="hook",
        generation_id="gen-1",
        observability_sink=sink,
    )
    assert report["trace"]["reviewRoute"] == "hard_gate"
    assert "modelCallId" not in report["trace"]
    assert list((tmp_path / "projects").glob("**/model-calls/*.json")) == []


def test_record_material_review_tool_run(tmp_path: Path) -> None:
    sink = LocalFileSink(AgentRunStore(tmp_path), ModelCallStore(tmp_path))
    tool_id = record_material_review_tool_run(
        sink=sink,
        project_id="project-1",
        task_id="task-1",
        generation_id="gen-1",
        slot_id="hook",
        preview_path="/tmp/preview.mp4",
        ok=True,
        report={
            "approved": True,
            "issues": [],
            "trace": {"reviewRoute": "video", "modelCallId": "call-1", "agentRunId": "run-1"},
        },
        parent_observability_run_id="acp-parent",
    )
    tool_path = tmp_path / "projects" / "project-1" / "logs" / "tool-runs" / f"{tool_id}.json"
    payload = json.loads(tool_path.read_text(encoding="utf-8"))
    assert payload["toolName"] == "review_material_preview"
    assert payload["metadata"]["parentObservabilityRunId"] == "acp-parent"


def test_run_slot_review_text_only_trace_includes_agent_run_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    generation_root = tmp_path / "projects" / "project-1" / "generations" / "gen-1"
    generation_root.mkdir(parents=True)
    preview = generation_root / "preview.mp4"
    preview.write_bytes(b"\x00" * 2048)

    sink = LocalFileSink(AgentRunStore(tmp_path), ModelCallStore(tmp_path))
    gateway = ModelGateway(config=_gateway_config())
    setup_material_review_observability(
        storage_root=tmp_path,
        project_id="project-1",
        task_id="task-1",
        generation_id="gen-1",
        slot_id="hook",
        gateway=gateway,
        sink=sink,
    )
    llm = LLMTool(fixture_mode=False, gateway=gateway)
    runner = AgentRunner(
        llm=llm,
        prompt_loader=PromptLoader(),
        observability_sink=sink,
        model_name="gpt-test",
    )

    class FakeFFmpeg:
        def probe(self, _path: Path) -> dict:
            return {"durationSec": 3.0}

    monkeypatch.setattr("app.pipelines.material_review.FFmpegTool", FakeFFmpeg)
    monkeypatch.setattr(
        "app.pipelines.material_review.resolve_material_review_route",
        lambda **_: "text_only",
    )

    def _fake_run(_self, agent_name, **kwargs):  # noqa: ANN001
        _self.last_agent_run_id = "agent-run-text-only"
        return {"approved": True, "issues": [], "suggestions": []}

    monkeypatch.setattr(AgentRunner, "run", _fake_run)

    context = TaskContext(
        task_id="task-1",
        project_id="project-1",
        storage_root=tmp_path,
    )
    report = run_slot_review(
        runner=runner,
        context=context,
        gateway=gateway,
        store=None,
        preview_path=preview,
        spec={"template": "composition", "durationSec": 3.0},
        author_payload={"projectId": "project-1", "taskId": "task-1"},
        slot_id="hook",
        generation_id="gen-1",
        generation_root=generation_root,
        observability_sink=sink,
    )

    assert report["trace"]["reviewRoute"] == "text_only"
    assert report["trace"]["agentRunId"] == "agent-run-text-only"
