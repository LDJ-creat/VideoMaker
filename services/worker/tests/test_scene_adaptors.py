from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from app.agents.prompt_loader import PromptLoader
from app.agents.runner import AgentRunner
from app.agents.scene_script_adaptor import run_scene_script_adaptor
from app.agents.scene_visual_adaptor import run_scene_visual_adaptor
from app.runtime.task_context import TaskContext
from app.tools.llm_tool import LLMTool, load_agent_fixtures


def _fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures" / "agents"


def _runner() -> AgentRunner:
    return AgentRunner(
        llm=LLMTool(fixture_mode=True, fixtures=load_agent_fixtures(_fixtures_dir())),
        prompt_loader=PromptLoader(),
        observability_sink=MagicMock(),
        model_name="fixture",
    )


def test_scene_visual_adaptor_returns_brief_with_timing_context(tmp_path: Path) -> None:
    context = TaskContext(project_id="proj-1", task_id="task-1", storage_root=tmp_path)
    runner = _runner()
    scene = {
        "slotId": "slot-1",
        "script": "测试口播",
        "visual": "产品特写",
        "compositionAuthorBrief": {"mode": "hf_native", "authorPrompt": "基础 brief"},
    }
    output = run_scene_visual_adaptor(
        runner,
        scene=scene,
        timing={
            "estimatedSec": 5.0,
            "measuredSec": 2.1,
            "driftRatio": 0.42,
            "charsPerSec": 4.0,
            "motionDensity": "compact",
            "beatCount": 2,
        },
        slot_role="hook",
        visual_style_bible={"summary": "暖色生活感"},
        structure_slot={"id": "slot-1", "role": "hook"},
        drift_warnings=["drift_strong"],
        context=context,
        generation_id="gen-1",
    )
    brief = output["compositionAuthorBrief"]
    assert brief["timingContext"]["measuredDurationSec"] == 2.1
    assert "时长适配" in brief["authorPrompt"]


def test_scene_script_adaptor_updates_script_and_master(tmp_path: Path) -> None:
    context = TaskContext(project_id="proj-1", task_id="task-1", storage_root=tmp_path)
    runner = _runner()
    output = run_scene_script_adaptor(
        runner,
        target_slot_id="slot-1",
        scene={"slotId": "slot-1", "script": "很长的口播文案需要压缩"},
        master_narration="很长的口播文案需要压缩。后续内容。",
        timing={
            "estimatedSec": 5.0,
            "measuredSec": 2.5,
            "driftRatio": 0.5,
            "wpmBudget": {"min": 8, "max": 12},
            "charsPerSec": 6.0,
        },
        slot_role="hook",
        duration_target_sec=30.0,
        visual_style_bible=None,
        instruction=None,
        context=context,
        generation_id="gen-1",
    )
    assert output["script"]
    assert output["masterNarration"]
    assert "compositionAuthorBrief" not in output
