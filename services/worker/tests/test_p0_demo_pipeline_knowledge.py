from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.agents.prompt_loader import PromptLoader
from app.agents.runner import AgentRunner
from app.gateway.providers.base import GatewayError
from app.knowledge.deposit import deposit_knowledge_draft
from app.knowledge.skill_writer import write_knowledge_draft
from app.observability.sink import build_observability_sink
from app.pipelines.p0_demo_pipeline import P0DemoPipeline
from app.runtime.task_context import TaskContext
from app.tools.llm_tool import LLMTool, load_agent_fixtures

def _structure() -> dict:
    return json.loads(
        (Path(__file__).parent / "fixtures" / "structures" / "sample-structure.json").read_text(
            encoding="utf-8"
        )
    )


def test_write_knowledge_draft(tmp_path: Path) -> None:
    uris = write_knowledge_draft(
        tmp_path,
        project_id="project-1",
        sample_id="sample-1",
        structure=_structure(),
        skill_output={
            "frontmatter": {
                "title": "测试",
                "category": "电商",
                "style": "快节奏",
                "summary": "摘要",
            },
            "markdown": "## 适用场景\n\n测试\n",
        },
    )
    skill_path = tmp_path / uris["skillMdUri"]
    assert skill_path.is_file()
    assert "适用场景" in skill_path.read_text(encoding="utf-8")


def test_write_knowledge_draft_uses_sample_analysis_has_bgm(tmp_path: Path) -> None:
    uris = write_knowledge_draft(
        tmp_path,
        project_id="project-1",
        sample_id="sample-1",
        structure=_structure(),
        skill_output={
            "frontmatter": {
                "title": "测试",
                "category": "电商",
                "style": "快节奏",
                "summary": "摘要",
            },
            "markdown": "## 适用场景\n\n测试\n",
        },
        sample_analysis={
            "audioProfile": {
                "hasVoiceover": True,
                "hasBgm": True,
                "metrics": {"voiceoverCoveragePct": 0.8},
            }
        },
    )
    meta_path = tmp_path / uris["entryMetaUri"]
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert meta["hasBgm"] is True


def test_deposit_knowledge_draft(tmp_path: Path) -> None:
    fixtures = load_agent_fixtures(Path(__file__).parent / "fixtures" / "agents")
    runner = AgentRunner(
        llm=LLMTool(fixture_mode=True, fixtures=fixtures),
        prompt_loader=PromptLoader(),
        observability_sink=build_observability_sink(tmp_path),
        model_name="fixture",
    )
    context = TaskContext(project_id="project-1", task_id="task-1", storage_root=tmp_path)
    result = deposit_knowledge_draft(
        runner,
        storage_root=tmp_path,
        project_id="project-1",
        sample_id="sample-1",
        structure=_structure(),
        sample_analysis={"metadata": {"durationSec": 30}},
        context=context,
    )
    draft = tmp_path / "projects" / "project-1" / "knowledge" / "drafts" / "sample-1" / "structure-skill.md"
    assert draft.is_file()
    assert result["uris"]["skillMdUri"]


def test_render_knowledge_draft_fails_when_agent_invalid(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fixtures = load_agent_fixtures(Path(__file__).parent / "fixtures" / "agents")
    pipeline = P0DemoPipeline(
        tmp_path,
        llm=LLMTool(fixture_mode=True, fixtures=fixtures),
    )
    analysis_root = tmp_path / "projects" / "project-1" / "samples" / "sample-1" / "analysis"
    analysis_root.mkdir(parents=True, exist_ok=True)
    structure = _structure()
    (analysis_root / "video-structure.json").write_text(
        json.dumps(structure, ensure_ascii=False),
        encoding="utf-8",
    )
    (analysis_root / "sample-analysis.json").write_text(
        json.dumps({"metadata": {"durationSec": 30}}, ensure_ascii=False),
        encoding="utf-8",
    )

    def _raise_invalid_json(*_args, **_kwargs):
        raise GatewayError(code="invalid_json", message="Model output is not valid JSON", retryable=False)

    monkeypatch.setattr(
        "app.pipelines.p0_demo_pipeline.deposit_knowledge_draft",
        _raise_invalid_json,
    )

    events: list[dict] = []

    def emit(**kwargs):
        events.append(kwargs)
        return kwargs

    result = pipeline.render_knowledge_draft(
        project_id="project-1",
        task_id="task-draft",
        sample_id="sample-1",
        emit=emit,
    )

    assert result["ok"] is False
    assert result["finalEvent"]["stage"] == "rendering_knowledge_draft"
    assert events[-1]["status"] == "failed"
    assert events[-1]["error"]["code"] == "invalid_json"
    draft = tmp_path / "projects" / "project-1" / "knowledge" / "drafts" / "sample-1"
    assert not (draft / "structure-skill.md").is_file()
