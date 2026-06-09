from __future__ import annotations

from app.pipelines.intent_applier import compute_affected_stages
from app.pipelines.revise_plan_builder import build_planner_output_from_rules


def test_subtitle_patch_skips_storyboard_and_material_stages() -> None:
    intents = [
        {
            "target": "generation_plan.packaging",
            "operation": "reduce_subtitles",
            "params": {},
            "rationale": "减少字幕",
            "executionTool": "subtitle_patch",
        }
    ]
    stages = compute_affected_stages(intents)
    assert "mapping_slots" not in stages
    assert "generating_material" not in stages
    assert "planning_completion" in stages
    assert "building_timeline" in stages
    assert "rendering" in stages


def test_timeline_scene_patch_skips_packaging_agent_stages() -> None:
    intents = [
        {
            "target": "generation_plan.storyboard",
            "operation": "timeline_scene_patch",
            "params": {"sceneId": "s1", "deltaSec": 1},
            "rationale": "延长",
            "executionTool": "timeline_scene_patch",
        }
    ]
    stages = compute_affected_stages(intents)
    assert stages == ["building_timeline", "rendering"]


def test_hook_adjustment_forks_full_pipeline_stages() -> None:
    plan = {
        "variant": "high_click",
        "storyboard": [{"id": "s1", "slotId": "slot-1", "startSec": 0, "endSec": 3, "script": "hi"}],
        "timeline": {"durationSec": 10.0, "tracks": []},
        "packagingPlan": {"subtitle": {"density": "medium"}},
    }
    output = build_planner_output_from_rules("开头更抓人一些", plan)
    assert output["executionMode"] == "fork"
    assert output["costTier"] in {"medium", "high"}
    stages = compute_affected_stages(output["intents"])
    assert "mapping_slots" in stages or "drafting_storyboard" in stages
