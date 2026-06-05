from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.agents.prompt_loader import PromptLoader
from app.agents.runner import AgentRunner
from app.knowledge.deposit import deposit_knowledge_draft
from app.knowledge.skill_writer import write_knowledge_draft
from app.observability.sink import build_observability_sink
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
