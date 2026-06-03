from __future__ import annotations

from app.pipelines.narration_script import (
    is_creative_direction_text,
    sanitize_storyboard_narration,
)
from app.agents.storyboard_writer import _assert_storyboard


def test_is_creative_direction_text_detects_slot_duplicate() -> None:
    slot = {
        "visualIntent": "Present a catchy headline that grabs viewer attention.",
        "scriptIntent": "Present a catchy headline that grabs viewer attention.",
    }
    assert is_creative_direction_text(
        "Present a catchy headline that grabs viewer attention.",
        slot=slot,
    )


def test_sanitize_storyboard_narration_clears_direction_without_transcript(
    tmp_path,
) -> None:
    del tmp_path  # unused; kept for signature compatibility if extended later
    structure = {
        "sourceVideoId": "sample-1",
        "slots": [
            {
                "id": "slot1",
                "visualIntent": "Present a catchy headline that grabs viewer attention.",
                "scriptIntent": "Present a catchy headline that grabs viewer attention.",
            }
        ],
    }
    storyboard = [
        {
            "id": "scene1",
            "slotId": "slot1",
            "startSec": 0.0,
            "endSec": 5.0,
            "visual": "Present a catchy headline that grabs viewer attention.",
            "script": "Present a catchy headline that grabs viewer attention.",
            "source": "generated",
        }
    ]
    sanitized = sanitize_storyboard_narration(storyboard, structure=structure)
    assert sanitized[0]["script"] == ""


def test_sanitize_storyboard_narration_keeps_valid_script() -> None:
    structure = {
        "slots": [
            {
                "id": "slot1",
                "visualIntent": "产品特写",
                "scriptIntent": "强调 SPF50",
            }
        ]
    }
    storyboard = [
        {
            "id": "scene1",
            "slotId": "slot1",
            "startSec": 0.0,
            "endSec": 5.0,
            "visual": "产品特写",
            "script": "夏天出门，防晒一定要选高倍数的。",
            "source": "generated",
        }
    ]
    sanitized = sanitize_storyboard_narration(storyboard, structure=structure)
    assert sanitized[0]["script"] == "夏天出门，防晒一定要选高倍数的。"


def test_assert_storyboard_clears_direction_script() -> None:
    structure = {
        "slots": [
            {
                "id": "slot-hook",
                "startSec": 0.0,
                "endSec": 3.0,
                "visualIntent": "Present a catchy headline that grabs viewer attention.",
                "scriptIntent": "Present a catchy headline that grabs viewer attention.",
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
                    "visual": "Present a catchy headline that grabs viewer attention.",
                    "script": "Present a catchy headline that grabs viewer attention.",
                    "source": "generated",
                }
            ],
        },
        structure=structure,
    )
    assert payload["storyboard"][0]["script"] == "夏天出门怕晒黑？"
