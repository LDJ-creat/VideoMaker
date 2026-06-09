from __future__ import annotations

from app.pipelines.revise_patch_executor import apply_timeline_scene_patch


def test_apply_timeline_scene_patch_ripples_downstream() -> None:
    plan = {
        "storyboard": [
            {"id": "s1", "slotId": "slot-1", "startSec": 0, "endSec": 3, "script": "a"},
            {"id": "s2", "slotId": "slot-2", "startSec": 3, "endSec": 6, "script": "b"},
        ],
        "timeline": {"durationSec": 6.0, "tracks": []},
    }
    intents = [
        {
            "target": "generation_plan.storyboard",
            "operation": "timeline_scene_patch",
            "params": {"sceneId": "s1", "newEndSec": 5, "ripple": True},
            "rationale": "延长第一镜",
            "executionTool": "timeline_scene_patch",
        }
    ]
    updated = apply_timeline_scene_patch(plan, intents)
    scenes = updated["storyboard"]
    assert scenes[0]["endSec"] == 5.0
    assert scenes[1]["startSec"] == 5.0
    assert scenes[1]["endSec"] == 8.0


def test_apply_timeline_scene_patch_new_end_sec() -> None:
    plan = {
        "storyboard": [
            {"id": "s1", "slotId": "slot-1", "startSec": 0, "endSec": 4, "script": "a"},
        ],
        "timeline": {"durationSec": 4.0, "tracks": []},
    }
    intents = [
        {
            "target": "generation_plan.storyboard",
            "operation": "timeline_scene_patch",
            "params": {"sceneId": "s1", "newEndSec": 2.5, "ripple": False},
            "rationale": "缩短",
            "executionTool": "timeline_scene_patch",
        }
    ]
    updated = apply_timeline_scene_patch(plan, intents)
    assert updated["storyboard"][0]["endSec"] == 2.5
