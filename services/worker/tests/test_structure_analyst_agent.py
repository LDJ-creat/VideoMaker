from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.agents.prompt_loader import PromptLoader
from app.agents.runner import AgentRunner
from app.agents.structure_analyst import run_structure_analyst
from app.observability.sink import LocalFileSink
from app.runtime.agent_run_store import AgentRunStore
from app.runtime.task_context import TaskContext
from app.tools.llm_tool import LLMTool, LLMToolValidationError, load_agent_fixtures
from app.validation.structure_validator import StructureValidationError


def _fixture_analysis() -> dict:
    path = Path(__file__).parent / "fixtures" / "sample_analysis.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_run_structure_analyst_fixture_mode_with_validator(tmp_path: Path) -> None:
    fixtures_dir = Path(__file__).parent / "fixtures" / "agents"
    runner = AgentRunner(
        llm=LLMTool(fixture_mode=True, fixtures=load_agent_fixtures(fixtures_dir)),
        prompt_loader=PromptLoader(),
        observability_sink=LocalFileSink(AgentRunStore(tmp_path)),
    )
    context = TaskContext(project_id="project-1", task_id="task-1", storage_root=tmp_path)
    analysis = _fixture_analysis()

    structure = run_structure_analyst(
        runner,
        analysis=analysis,
        context=context,
        project_id="project-1",
        source_video_id="sample-1",
        analysis_root=None,
    )

    assert structure["projectId"] == "project-1"
    assert structure["sourceVideoId"] == "sample-1"
    assert structure["evidence"]
    segment_ids = {segment["id"] for segment in structure["narrative"]["segments"]}
    evidenced = {item["targetId"] for item in structure["evidence"] if item["targetId"] in segment_ids}
    assert evidenced == segment_ids


def test_run_structure_analyst_uses_vision_profile_when_keyframes_encoded(tmp_path: Path) -> None:
    analysis = _fixture_analysis()
    analysis_root = tmp_path / "projects" / "project-1" / "samples" / "sample-1" / "analysis"
    keyframes_dir = analysis_root / "keyframes"
    keyframes_dir.mkdir(parents=True)
    for item in analysis["keyframes"]:
        image_path = analysis_root / item["path"]
        image_path.parent.mkdir(parents=True, exist_ok=True)
        image_path.write_bytes(b"frame")

    fixture_output = load_agent_fixtures(Path(__file__).parent / "fixtures" / "agents")[
        "structure_analyst"
    ]
    gateway = MagicMock()
    gateway.complete_json_messages.return_value = fixture_output

    runner = AgentRunner(
        llm=LLMTool(fixture_mode=False, gateway=gateway),
        prompt_loader=PromptLoader(),
        observability_sink=LocalFileSink(AgentRunStore(tmp_path)),
        model_name="vision-test",
    )
    context = TaskContext(project_id="project-1", task_id="task-1", storage_root=tmp_path)

    run_structure_analyst(
        runner,
        analysis=analysis,
        context=context,
        project_id="project-1",
        source_video_id="sample-1",
        analysis_root=analysis_root,
    )

    _, kwargs = gateway.complete_json_messages.call_args
    assert kwargs["profile"] == "vision"
    messages = gateway.complete_json_messages.call_args[0][0]
    user_content = messages[1]["content"]
    assert user_content[0]["type"] == "text"
    assert any(part.get("type") == "image_url" for part in user_content)


def test_run_structure_analyst_repair_omits_images_on_second_attempt(tmp_path: Path) -> None:
    analysis = _fixture_analysis()
    analysis_root = tmp_path / "analysis"
    keyframes_dir = analysis_root / "keyframes"
    keyframes_dir.mkdir(parents=True)
    for item in analysis["keyframes"]:
        (analysis_root / item["path"]).write_bytes(b"frame")

    valid = load_agent_fixtures(Path(__file__).parent / "fixtures" / "agents")["structure_analyst"]
    broken = json.loads(json.dumps(valid))
    broken["evidence"] = []

    gateway = MagicMock()
    gateway.complete_json_messages.side_effect = [broken, valid]

    runner = AgentRunner(
        llm=LLMTool(fixture_mode=False, gateway=gateway),
        prompt_loader=PromptLoader(),
        observability_sink=LocalFileSink(AgentRunStore(tmp_path)),
    )
    context = TaskContext(project_id="project-1", task_id="task-1", storage_root=tmp_path)

    structure = run_structure_analyst(
        runner,
        analysis=analysis,
        context=context,
        project_id="project-1",
        source_video_id="sample-1",
        analysis_root=analysis_root,
    )

    assert structure["id"] == valid["id"]
    assert gateway.complete_json_messages.call_count == 2
    assert gateway.complete_json_messages.call_args_list[0].kwargs["profile"] == "vision"
    assert gateway.complete_json_messages.call_args_list[1].kwargs["profile"] == "text"
    second_messages = gateway.complete_json_messages.call_args_list[1][0][0]
    second_user = second_messages[1]["content"]
    assert isinstance(second_user, str)


def test_run_structure_analyst_fails_on_invalid_evidence_after_repair(tmp_path: Path) -> None:
    broken = load_agent_fixtures(Path(__file__).parent / "fixtures" / "agents")["structure_analyst"]
    broken["evidence"] = []

    gateway = MagicMock()
    gateway.complete_json_messages.return_value = broken

    runner = AgentRunner(
        llm=LLMTool(fixture_mode=False, gateway=gateway),
        prompt_loader=PromptLoader(),
        observability_sink=LocalFileSink(AgentRunStore(tmp_path)),
    )
    context = TaskContext(project_id="project-1", task_id="task-1", storage_root=tmp_path)

    with pytest.raises(StructureValidationError):
        run_structure_analyst(
            runner,
            analysis=_fixture_analysis(),
            context=context,
            project_id="project-1",
            source_video_id="sample-1",
        )

    assert gateway.complete_json_messages.call_count == 2


def test_run_structure_analyst_persists_schema_failure_debug(tmp_path: Path) -> None:
    analysis = _fixture_analysis()
    analysis_root = tmp_path / "projects" / "project-1" / "samples" / "sample-1" / "analysis"
    keyframes_dir = analysis_root / "keyframes"
    keyframes_dir.mkdir(parents=True)
    for item in analysis["keyframes"]:
        (analysis_root / item["path"]).write_bytes(b"frame")

    gateway = MagicMock()
    gateway.complete_json_messages.return_value = {"id": "partial-structure"}

    runner = AgentRunner(
        llm=LLMTool(fixture_mode=False, gateway=gateway),
        prompt_loader=PromptLoader(),
        observability_sink=LocalFileSink(AgentRunStore(tmp_path)),
    )
    context = TaskContext(project_id="project-1", task_id="task-1", storage_root=tmp_path)

    with pytest.raises(LLMToolValidationError):
        run_structure_analyst(
            runner,
            analysis=analysis,
            context=context,
            project_id="project-1",
            source_video_id="sample-1",
            analysis_root=analysis_root,
        )

    failure_path = analysis_root / "structure-agent-failure.json"
    assert failure_path.is_file()
    summary = json.loads(failure_path.read_text(encoding="utf-8"))
    assert summary["errorType"] == "LLMToolValidationError"
    assert summary["validationErrors"]
    assert (analysis_root / "structure-llm-raw-output.json").is_file()

    agent_logs = list(
        (tmp_path / "projects" / "project-1" / "logs" / "agent-runs").glob("*.json")
    )
    assert agent_logs
    agent_payload = json.loads(agent_logs[-1].read_text(encoding="utf-8"))
    assert agent_payload["outputValid"] is False
    assert agent_payload["validationErrors"]
