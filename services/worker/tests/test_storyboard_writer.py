from __future__ import annotations

from app.agents.storyboard_writer import _assert_storyboard


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
            "storyboard": [
                {
                    "slotId": "slot-hook",
                    "startSec": 0.0,
                    "endSec": 3.0,
                    "visual": "hook visual",
                    "script": "hook script",
                    "source": "generated",
                }
            ]
        },
        structure=structure,
    )
    assert payload["storyboard"][0]["id"] == "scene-slot-hook"
