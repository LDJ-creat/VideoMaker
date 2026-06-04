from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.agents.knowledge_author import run_knowledge_author
from app.agents.prompt_loader import PromptLoader
from app.agents.runner import AgentRunner
from app.observability.sink import build_observability_sink
from app.runtime.task_context import TaskContext
from app.tools.llm_tool import LLMTool, load_agent_fixtures


def _structure() -> dict:
    path = Path(__file__).parent / "fixtures" / "structures" / "sample-structure.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_run_knowledge_author_fixture(tmp_path: Path) -> None:
    fixtures = load_agent_fixtures(Path(__file__).parent / "fixtures" / "agents")
    runner = AgentRunner(
        llm=LLMTool(fixture_mode=True, fixtures=fixtures),
        prompt_loader=PromptLoader(),
        observability_sink=build_observability_sink(tmp_path),
        model_name="fixture",
    )
    context = TaskContext(project_id="p1", task_id="t1", storage_root=tmp_path)
    output = run_knowledge_author(
        runner,
        structure=_structure(),
        sample_analysis={"metadata": {"durationSec": 30}},
        context=context,
    )
    assert output["frontmatter"]["title"]
    assert "## 适用场景" in output["markdown"]
