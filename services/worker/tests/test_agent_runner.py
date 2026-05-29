from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.agents.prompt_loader import PromptLoader
from app.agents.runner import AgentRunner
from app.observability.sink import LocalFileSink
from app.runtime.agent_run_store import AgentRunStore
from app.runtime.task_context import TaskContext
from app.tools.llm_tool import LLMTool, LLMToolConfigError, LLMToolValidationError, load_agent_fixtures


def _fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures" / "agents"


def test_prompt_loader_loads_structure_analyst() -> None:
    loader = PromptLoader()
    content = loader.load("structure_analyst")
    assert content.strip()
    assert len(loader.version("structure_analyst")) == 8


def test_agent_run_store_record_creates_log_file(tmp_path: Path) -> None:
    store = AgentRunStore(tmp_path)
    from app.runtime.agent_run_store import AgentRunLog

    log_path = store.record(
        project_id="project-1",
        log=AgentRunLog(
            agent_name="structure_analyst",
            prompt_version="abc12345",
            model="fixture",
            task="structure_analyst",
            input_summary="{}",
            output_valid=True,
            latency_ms=12.5,
            task_id="task-1",
        ),
    )
    payload = json.loads(log_path.read_text(encoding="utf-8"))
    assert payload["agentName"] == "structure_analyst"
    assert payload["outputValid"] is True
    assert payload["taskId"] == "task-1"


def test_agent_runner_fixture_mode_returns_valid_structure(tmp_path: Path) -> None:
    runner = AgentRunner(
        llm=LLMTool(fixture_mode=True, fixtures=load_agent_fixtures(_fixtures_dir())),
        prompt_loader=PromptLoader(),
        observability_sink=LocalFileSink(AgentRunStore(tmp_path)),
    )
    context = TaskContext(project_id="project-1", task_id="task-1", storage_root=tmp_path)
    output = runner.run(
        "structure_analyst",
        task="structure_analyst",
        schema_name="video-structure",
        inputs={"analysis": {}},
        context=context,
    )
    assert output["projectId"] == "project-1"


def test_agent_runner_invalid_fixture_raises_and_logs_failure(tmp_path: Path) -> None:
    runner = AgentRunner(
        llm=LLMTool(fixture_mode=True, fixtures={"structure_analyst": {"id": "bad"}}),
        prompt_loader=PromptLoader(),
        observability_sink=LocalFileSink(AgentRunStore(tmp_path)),
    )
    context = TaskContext(project_id="project-1", task_id="task-1", storage_root=tmp_path)
    with pytest.raises(LLMToolValidationError):
        runner.run(
            "structure_analyst",
            task="structure_analyst",
            schema_name="video-structure",
            inputs={},
            context=context,
        )

    log_dir = tmp_path / "projects" / "project-1" / "logs" / "agent-runs"
    logs = list(log_dir.glob("*.json"))
    assert logs
    payload = json.loads(logs[0].read_text(encoding="utf-8"))
    assert payload["outputValid"] is False
    assert payload["validationErrors"]


def test_agent_runner_missing_fixture_raises_config_error(tmp_path: Path) -> None:
    runner = AgentRunner(
        llm=LLMTool(fixture_mode=True, fixtures={}),
        prompt_loader=PromptLoader(),
        observability_sink=LocalFileSink(AgentRunStore(tmp_path)),
    )
    context = TaskContext(project_id="project-1", task_id="task-1", storage_root=tmp_path)
    with pytest.raises(LLMToolConfigError):
        runner.run(
            "structure_analyst",
            task="structure_analyst",
            schema_name="video-structure",
            inputs={},
            context=context,
        )


def test_agent_runner_post_validate_failure_logs_invalid_output(tmp_path: Path) -> None:
    runner = AgentRunner(
        llm=LLMTool(
            fixture_mode=True,
            fixtures={"slot_mapper": {"slotMatches": [{"slotId": "only-id"}]}},
        ),
        prompt_loader=PromptLoader(),
        observability_sink=LocalFileSink(AgentRunStore(tmp_path)),
    )
    context = TaskContext(project_id="project-1", task_id="task-1", storage_root=tmp_path)

    def bad_validate(payload: dict) -> dict:
        raise ValueError("invalid slot match shape")

    with pytest.raises(ValueError, match="invalid slot match shape"):
        runner.run(
            "slot_mapper",
            task="slot_mapper",
            schema_name=None,
            inputs={},
            context=context,
            post_validate=bad_validate,
        )

    log_dir = tmp_path / "projects" / "project-1" / "logs" / "agent-runs"
    payload = json.loads(next(log_dir.glob("*.json")).read_text(encoding="utf-8"))
    assert payload["outputValid"] is False
    assert payload["validationErrors"]
