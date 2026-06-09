from __future__ import annotations

from pathlib import Path

from app.agents.composition_pattern_author import run_composition_pattern_author
from app.agents.prompt_loader import PromptLoader
from app.agents.runner import AgentRunner
from app.observability.sink import build_observability_sink
from app.runtime.task_context import TaskContext
from app.tools.llm_tool import LLMTool, load_agent_fixtures


def test_run_composition_pattern_author_fixture(tmp_path: Path) -> None:
    fixtures = load_agent_fixtures(Path(__file__).parent / "fixtures" / "agents")
    runner = AgentRunner(
        llm=LLMTool(fixture_mode=True, fixtures=fixtures),
        prompt_loader=PromptLoader(),
        observability_sink=build_observability_sink(tmp_path),
        model_name="fixture",
    )
    context = TaskContext(
        project_id="project-1",
        task_id="task-1",
        storage_root=tmp_path,
    )
    output = run_composition_pattern_author(
        runner,
        material_spec={
            "template": "composition",
            "durationSec": 2,
            "composition": {"bodyHtml": '<div id="root">{{title}}</div>'},
        },
        instance_spec={
            "template": "composition",
            "durationSec": 2,
            "composition": {"bodyHtml": '<div id="root">原始</div>'},
        },
        slot={"slotId": "slot-1", "role": "benefit_card", "storyboardSummary": "卖点"},
        context=context,
    )
    assert output["frontmatter"]["title"]
    assert output["materialSpec"]["template"] == "composition"
