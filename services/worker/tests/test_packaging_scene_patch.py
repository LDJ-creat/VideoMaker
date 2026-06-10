from __future__ import annotations

import json

from app.pipelines.revise_patch_executor import (    apply_fork_packaging_scene_patches,
    apply_packaging_scene_patch,
)


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


def test_apply_fork_packaging_scene_patches_reads_edit_intent(tmp_path) -> None:
    generation_root = tmp_path / "gen-target"
    generation_root.mkdir(parents=True)
    plan = {
        "storyboard": [
            {
                "id": "scene-6",
                "slotId": "slot-6",
                "startSec": 15.0,
                "endSec": 18.0,
                "script": "结尾",
                "source": "user_asset",
                "visual": "ending",
            }
        ],
        "packagingPlan": {"subtitle": {"preset": "clean"}},
        "timeline": {"durationSec": 18.0, "tracks": []},
    }
    (generation_root / "generation-plan.json").write_text("{}", encoding="utf-8")
    (generation_root / "structure-scaled.json").write_text(
        json.dumps(
            {
                "slots": [
                    {
                        "id": "slot-6",
                        "role": "cta_visual",
                        "startSec": 15.0,
                        "endSec": 18.0,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (generation_root / "slot-matches.json").write_text(
        json.dumps({"slotMatches": [{"slotId": "slot-6", "assetId": "asset-1"}]}),
        encoding="utf-8",
    )
    (generation_root / "asset-inventory.json").write_text('{"assets": []}', encoding="utf-8")
    (generation_root / "edit-intent.json").write_text(
        """
        {
          "intents": [
            {
              "operation": "packaging_scene_patch",
              "executionTool": "packaging_scene_patch",
              "params": {"sceneId": "scene-6", "backgroundPreset": "dark"}
            }
          ]
        }
        """.strip(),
        encoding="utf-8",
    )
    updated = apply_fork_packaging_scene_patches(plan, generation_root)
    overlays = updated["packagingPlan"]["sceneOverlays"]
    assert len(overlays) == 1
    assert overlays[0]["backgroundPreset"] == "dark"
    overlay_clips = [
        clip
        for track in updated["timeline"]["tracks"]
        if track.get("type") == "text"
        for clip in track.get("clips", [])
        if str(clip.get("id", "")).startswith("overlay-")
    ]
    assert len(overlay_clips) == 1
