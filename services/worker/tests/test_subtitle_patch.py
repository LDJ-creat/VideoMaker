from __future__ import annotations

import json
from pathlib import Path

from app.pipelines.revise_patch_executor import apply_subtitle_patch


def test_apply_subtitle_patch_reduces_density() -> None:
    plan = {
        "storyboard": [
            {
                "id": "scene-1",
                "slotId": "slot-1",
                "startSec": 0,
                "endSec": 3,
                "script": "第一句。第二句。",
            }
        ],
        "timeline": {
            "durationSec": 3.0,
            "tracks": [
                {
                    "id": "track-text",
                    "type": "text",
                    "clips": [
                        {
                            "id": "subtitle-slot-1",
                            "startSec": 0,
                            "endSec": 3,
                            "content": "old",
                            "styleRef": "style://subtitle/clean",
                        }
                    ],
                }
            ],
        },
        "packagingPlan": {"subtitle": {"density": "medium", "preset": "clean"}},
        "ttsMode": "per_scene",
    }
    intents = [
        {
            "target": "generation_plan.packaging",
            "operation": "reduce_subtitles",
            "params": {},
            "rationale": "减少字幕",
            "executionTool": "subtitle_patch",
        }
    ]
    updated = apply_subtitle_patch(plan, intents)
    assert updated["packagingPlan"]["subtitle"]["density"] == "low"
    text_track = next(t for t in updated["timeline"]["tracks"] if t["type"] == "text")
    subtitle_clips = [c for c in text_track["clips"] if str(c.get("id", "")).startswith("subtitle-")]
    assert subtitle_clips
