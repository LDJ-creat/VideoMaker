from __future__ import annotations

from app.pipelines.revise_patch_executor import apply_packaging_scene_patch


def test_apply_packaging_scene_patch_updates_scene_overlay() -> None:
    plan = {
        "storyboard": [
            {
                "id": "scene-6",
                "slotId": "slot-6",
                "startSec": 15.0,
                "endSec": 18.0,
                "script": "结尾",
            }
        ],
        "packagingPlan": {
            "styleSummary": "demo",
            "subtitle": {"preset": "clean"},
            "titleCards": [],
            "transitions": [],
        },
    }
    intents = [
        {
            "target": "generation_plan.packaging",
            "operation": "packaging_scene_patch",
            "params": {"sceneId": "scene-6", "backgroundPreset": "dark"},
            "rationale": "最后一镜包装背景",
            "executionTool": "packaging_scene_patch",
            "sceneIds": ["scene-6"],
        }
    ]
    updated = apply_packaging_scene_patch(plan, intents)
    overlays = updated["packagingPlan"]["sceneOverlays"]
    assert len(overlays) == 1
    assert overlays[0]["slotId"] == "slot-6"
    assert overlays[0]["backgroundPreset"] == "dark"
