from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.agents.prompt_loader import PromptLoader
from app.agents.runner import AgentRunner
from app.providers.completion_registry import register_default_providers
from app.providers.hyperframes_material_provider import HyperFramesMaterialProvider
from app.providers.material_types import MaterialContext
from app.observability.sink import LocalFileSink
from app.runtime.agent_run_store import AgentRunStore
from app.runtime.task_context import TaskContext
from app.tools.hyperframes_tool import CommandResult, HyperFramesTool
from app.tools.hyperframes_material_tool import HyperFramesMaterialTool
from app.tools.llm_tool import LLMTool


def _load_structure_fixture() -> dict:
    fixture_path = Path(__file__).parent / "fixtures" / "structures" / "sample-structure.json"
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def _load_material_spec_fixture() -> dict:
    fixture_path = Path(__file__).parent / "fixtures" / "material_specs" / "benefit_card.json"
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def _mock_cli_runner() -> HyperFramesTool:
    def runner(command: list[str], cwd: Path) -> CommandResult:
        if "render" in command:
            output_index = command.index("--output") + 1
            Path(command[output_index]).write_bytes(b"mock-mp4")
        return CommandResult(returncode=0, stdout="ok", stderr="")

    return HyperFramesTool(command_runner=runner)


def _project_layout(tmp_path: Path) -> tuple[Path, Path, Path]:
    project_root = tmp_path / "projects" / "project-1"
    generated_root = project_root / "generations" / "gen-1" / "generated"
    render_root = project_root / "renders" / "gen-1"
    generated_root.mkdir(parents=True, exist_ok=True)
    render_root.mkdir(parents=True, exist_ok=True)
    return project_root, generated_root, render_root


def _make_hf_ctx(
    tmp_path: Path,
    *,
    structure: dict,
    runner: AgentRunner | None = None,
    task_context: TaskContext | None = None,
    material_tool: HyperFramesMaterialTool | None = None,
) -> MaterialContext:
    project_root, generated_root, render_root = _project_layout(tmp_path)
    progress_events: list[tuple[str, str]] = []

    ctx = MaterialContext(
        project_id="project-1",
        generation_id="gen-1",
        render_root=render_root,
        generated_root=generated_root,
        gateway=MagicMock(),
        quota=MagicMock(),
        inventory={"assets": []},
        slot_matches=[],
        storyboard=[],
        structure=structure,
        emit_progress=lambda stage, message: progress_events.append((stage, message)),
        register_artifact=lambda artifact_type, path: {
            "id": "art-hf-1",
            "type": artifact_type,
            "uri": str(Path(path).resolve()),
            "createdAt": "2026-05-29T00:00:00Z",
        },
        runner=runner,
        task_context=task_context,
    )
    register_default_providers(ctx)
    if material_tool is not None:
        ctx.providers["hyperframes_material"] = HyperFramesMaterialProvider(material_tool)
    ctx._progress_events = progress_events  # type: ignore[attr-defined]
    return ctx


def test_hyperframes_provider_with_prefilled_spec(tmp_path: Path) -> None:
    structure = _load_structure_fixture()
    material_tool = HyperFramesMaterialTool(hyperframes_tool=_mock_cli_runner())
    ctx = _make_hf_ctx(tmp_path, structure=structure, material_tool=material_tool)
    _, generated_root, _ = _project_layout(tmp_path)
    action = {
        "id": "action-benefit-card",
        "slotId": "seg-2-benefit_card-1",
        "provider": "hyperframes_material",
        "strategy": "hyperframes_material",
        "reason": "needs card",
        "outputRef": "completion://seg-2-benefit_card-1/hyperframes_material",
        "materialSpec": _load_material_spec_fixture(),
    }

    result = ctx.providers["hyperframes_material"].execute(action, ctx)

    assert result["ok"] is True
    assert result["artifactRef"]["type"] == "video"
    assert (generated_root / "action-benefit-card.mp4").exists()
    assert ctx._progress_events == [  # type: ignore[attr-defined]
        ("rendering_material", "HyperFrames material ready for slot seg-2-benefit_card-1")
    ]


def test_hyperframes_provider_runs_material_author_via_runner(tmp_path: Path) -> None:
    structure = _load_structure_fixture()
    spec = _load_material_spec_fixture()
    storage_root = tmp_path / "storage"
    task_context = TaskContext(
        project_id="project-1",
        task_id="task-hf",
        storage_root=storage_root,
    )
    agent_runner = AgentRunner(
        llm=LLMTool(fixture_mode=True, fixtures={"material_author": spec}),
        prompt_loader=PromptLoader(),
        observability_sink=LocalFileSink(AgentRunStore(storage_root)),
        model_name="fixture",
    )
    material_tool = HyperFramesMaterialTool(hyperframes_tool=_mock_cli_runner())
    ctx = _make_hf_ctx(
        tmp_path,
        structure=structure,
        runner=agent_runner,
        task_context=task_context,
        material_tool=material_tool,
    )
    action = {
        "id": "action-benefit-card",
        "slotId": "seg-2-benefit_card-1",
        "provider": "hyperframes_material",
        "strategy": "hyperframes_material",
        "reason": "needs card",
        "outputRef": "completion://seg-2-benefit_card-1/hyperframes_material",
    }

    result = ctx.providers["hyperframes_material"].execute(action, ctx)

    assert result["ok"] is True
    assert any(event["stage"] == "running_agent" for event in task_context.emitted_events)


def test_hyperframes_provider_render_failure_returns_structured_error(tmp_path: Path) -> None:
    structure = _load_structure_fixture()
    ctx = _make_hf_ctx(tmp_path, structure=structure)
    action = {
        "id": "action-benefit-card",
        "slotId": "seg-2-benefit_card-1",
        "provider": "hyperframes_material",
        "strategy": "hyperframes_material",
        "reason": "needs card",
        "outputRef": "completion://seg-2-benefit_card-1/hyperframes_material",
        "materialSpec": _load_material_spec_fixture(),
    }

    result = ctx.providers["hyperframes_material"].execute(action, ctx)

    assert result["ok"] is False
    assert result["error"]["code"] == "hyperframes_missing"


def test_hyperframes_provider_missing_runner_returns_error(tmp_path: Path) -> None:
    structure = _load_structure_fixture()
    ctx = _make_hf_ctx(tmp_path, structure=structure)
    action = {
        "id": "action-benefit-card",
        "slotId": "seg-2-benefit_card-1",
        "provider": "hyperframes_material",
        "strategy": "hyperframes_material",
        "reason": "needs card",
        "outputRef": "completion://seg-2-benefit_card-1/hyperframes_material",
    }

    result = ctx.providers["hyperframes_material"].execute(action, ctx)

    assert result["ok"] is False
    assert result["error"]["code"] == "material_author_unavailable"
