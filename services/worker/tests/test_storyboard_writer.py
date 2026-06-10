from __future__ import annotations

import pytest

from app.agents.storyboard_writer import (
    _assert_master_only,
    _assert_storyboard,
    _assert_storyboard_from_master,
    run_storyboard_writer,
    slim_structure_for_script,
)


def test_slim_structure_for_script_drops_evidence_and_shot_boundaries() -> None:
    structure = {
        "version": "p1-v3",
        "metadata": {"durationSec": 30.0},
        "slots": [{"id": "slot-1", "startSec": 0, "endSec": 3}],
        "verbal": {"hookTemplate": "hook"},
        "evidence": [{"targetId": "slot-1", "source": "asr"}],
        "rhythm": {
            "totalDurationSec": 30.0,
            "tempo": "fast",
            "shotBoundaries": [{"startSec": 0, "endSec": 1.0}],
        },
    }
    slim = slim_structure_for_script(structure)
    assert "evidence" not in slim
    assert "shotBoundaries" not in slim.get("rhythm", {})
    assert slim["rhythm"]["tempo"] == "fast"
    assert slim["verbal"]["hookTemplate"] == "hook"


def test_run_storyboard_writer_rejects_deprecated_full_phase() -> None:
    from app.agents.prompt_loader import PromptLoader
    from app.agents.runner import AgentRunner
    from app.observability.sink import LocalFileSink
    from app.runtime.agent_run_store import AgentRunStore
    from app.runtime.task_context import TaskContext
    from app.tools.llm_tool import LLMTool, load_agent_fixtures
    from pathlib import Path

    fixtures_dir = Path(__file__).parent / "fixtures" / "agents"
    runner = AgentRunner(
        llm=LLMTool(fixture_mode=True, fixtures=load_agent_fixtures(fixtures_dir)),
        prompt_loader=PromptLoader(),
        observability_sink=LocalFileSink(AgentRunStore(Path("/tmp/unused"))),
    )
    context = TaskContext(project_id="p1", task_id="t1", storage_root=Path("/tmp"))
    with pytest.raises(ValueError, match="deprecated"):
        run_storyboard_writer(
            runner,
            structure={"slots": []},
            inventory={"userBrief": {}},
            gap_report={},
            context=context,
            phase="full",
        )


def test_assert_master_only_preserves_narration_vo_profile() -> None:
    structure = {"slots": []}
    payload = _assert_master_only(
        {
            "masterNarration": "夏天出门怕晒黑？",
            "narrationVoProfile": {"pace": "fast", "energy": "high"},
        },
        structure=structure,
    )
    assert payload["narrationVoProfile"] == {"pace": "fast", "energy": "high"}


def test_assert_storyboard_from_master_applies_narration_timing() -> None:
    structure = {
        "slots": [
            {"id": "slot-1", "startSec": 0.0, "endSec": 10.0},
            {"id": "slot-2", "startSec": 10.0, "endSec": 20.0},
        ]
    }
    payload = _assert_storyboard_from_master(
        {
            "storyboard": [
                {
                    "slotId": "slot-1",
                    "startSec": 0.0,
                    "endSec": 10.0,
                    "visual": "v1",
                    "script": "第一句。",
                    "source": "generated",
                },
                {
                    "slotId": "slot-2",
                    "startSec": 10.0,
                    "endSec": 20.0,
                    "visual": "v2",
                    "script": "第二句。",
                    "source": "generated",
                },
            ],
        },
        structure=structure,
        master_narration="第一句。第二句。",
        narration_timing={
            "durationSec": 12.0,
            "sceneTiming": [
                {"slotId": "slot-1", "startSec": 0.0, "endSec": 5.0},
                {"slotId": "slot-2", "startSec": 5.0, "endSec": 12.0},
            ],
        },
    )
    assert payload["storyboard"][0]["endSec"] == 5.0
    assert payload["storyboard"][1]["endSec"] == 12.0


def test_assert_storyboard_from_master_preserves_vo_directive() -> None:
    structure = {
        "slots": [
            {
                "id": "slot-hook",
                "startSec": 0.0,
                "endSec": 3.0,
                "visualIntent": "hook visual",
                "scriptIntent": "hook script",
            }
        ]
    }
    payload = _assert_storyboard_from_master(
        {
            "storyboard": [
                {
                    "slotId": "slot-hook",
                    "startSec": 0.0,
                    "endSec": 3.0,
                    "visual": "hook visual",
                    "script": "夏天出门怕晒黑？",
                    "source": "generated",
                    "voDirective": {"pace": "fast", "contextHint": "疑问句上扬"},
                }
            ],
        },
        structure=structure,
        master_narration="夏天出门怕晒黑？",
    )
    assert payload["storyboard"][0]["voDirective"] == {
        "pace": "fast",
        "contextHint": "疑问句上扬",
    }


def test_assert_storyboard_fills_missing_scene_id() -> None:
    structure = {
        "slots": [
            {
                "id": "slot-hook",
                "startSec": 0.0,
                "endSec": 3.0,
                "visualIntent": "hook visual",
                "scriptIntent": "hook script",
            }
        ]
    }
    payload = _assert_storyboard(
        {
            "masterNarration": "夏天出门怕晒黑？",
            "storyboard": [
                {
                    "slotId": "slot-hook",
                    "startSec": 0.0,
                    "endSec": 3.0,
                    "visual": "hook visual",
                    "script": "夏天出门怕晒黑？",
                    "source": "generated",
                }
            ],
        },
        structure=structure,
    )
    assert payload["masterNarration"] == "夏天出门怕晒黑？"
    assert payload["storyboard"][0]["id"] == "scene-slot-hook"
    assert payload["storyboard"][0]["script"] == "夏天出门怕晒黑？"
