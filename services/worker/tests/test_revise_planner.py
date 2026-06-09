from __future__ import annotations

from pathlib import Path

from app.pipelines.revise_plan_builder import (
    build_planner_output_from_rules,
    enrich_revise_plan,
)


def test_build_planner_output_subtitle_low_cost() -> None:
    plan = {
        "variant": "high_click",
        "storyboard": [{"id": "s1", "slotId": "slot-1", "startSec": 0, "endSec": 3, "script": "hi"}],
        "timeline": {"durationSec": 10.0, "tracks": []},
        "packagingPlan": {"subtitle": {"density": "medium"}},
    }
    output = build_planner_output_from_rules("字幕少一点", plan)
    assert output["costTier"] == "low"
    assert output["executionMode"] == "in_place"
    assert output["intents"][0]["executionTool"] == "subtitle_patch"


def test_enrich_revise_plan_has_ids() -> None:
    plan = {
        "variant": "high_click",
        "storyboard": [],
        "timeline": {"durationSec": 10.0, "tracks": []},
        "packagingPlan": {"subtitle": {"density": "medium"}},
    }
    output = build_planner_output_from_rules("字幕少一点", plan)
    enriched = enrich_revise_plan(
        output,
        source_generation_id="gen-1",
        instruction="字幕少一点",
        session_id="session-1",
    )
    assert enriched["planId"]
    assert enriched["sessionId"] == "session-1"
    assert enriched["status"] == "draft"


def test_session_turns_lower_density_on_follow_up() -> None:
    plan = {
        "variant": "high_click",
        "storyboard": [{"id": "s1", "slotId": "slot-1", "startSec": 0, "endSec": 3, "script": "hi"}],
        "timeline": {"durationSec": 10.0, "tracks": []},
        "packagingPlan": {"subtitle": {"density": "medium"}},
    }
    first = build_planner_output_from_rules("字幕少一点", plan)
    session = {
        "sessionId": "session-1",
        "turns": [
            {
                "instruction": "字幕少一点",
                "planSummary": first["summary"],
                "status": "executed",
            }
        ],
        "conversationSummary": first["conversationSummary"],
    }
    from app.pipelines.revise_plan_builder import build_session_turns_for_planner

    turns = build_session_turns_for_planner(session)
    assert len(turns) == 1
    assert turns[0]["planSummary"]
    plan_after = dict(plan)
    plan_after["packagingPlan"] = {"subtitle": {"density": "low"}}
    second = build_planner_output_from_rules("减少字幕", plan_after)
    assert second["costTier"] == "low"
    assert second["executionMode"] == "in_place"
