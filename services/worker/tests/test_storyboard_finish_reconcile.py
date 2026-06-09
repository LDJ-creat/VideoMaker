from __future__ import annotations

from app.pipelines.storyboard_finish_reconcile import reconcile_gap_finish_from_storyboard


def test_storyboard_packaging_keyword_upgrades_finish_mode() -> None:
    gap_report = {
        "missingSlots": [
            {
                "slotId": "slot-hook",
                "reason": "missing",
                "impact": "high",
                "completionMode": "source_only",
                "suggestedFixes": ["stock_media_search"],
            }
        ],
        "weakSlots": [],
    }
    storyboard = [
        {
            "slotId": "slot-hook",
            "visual": "B-roll 饭局场景，叠加 lower third 字幕条",
            "script": "你是不是只会点头微笑？",
        }
    ]
    structure = {
        "slots": [
            {
                "id": "slot-hook",
                "role": "hook_visual",
                "packagingRequirements": [],
            }
        ]
    }
    updated = reconcile_gap_finish_from_storyboard(gap_report, storyboard=storyboard, structure=structure)
    item = updated["missingSlots"][0]
    assert item["completionMode"] == "source_then_polish"
    assert item["suggestedFixes"][-1] == "hyperframes_material"


def test_packaging_requirements_force_polish() -> None:
    gap_report = {
        "weakSlots": [
            {
                "slotId": "slot-card",
                "reason": "weak",
                "impact": "medium",
                "completionMode": "source_only",
                "suggestedFixes": ["hyperframes_material"],
            }
        ],
        "missingSlots": [],
    }
    structure = {
        "slots": [
            {
                "id": "slot-card",
                "role": "benefit_card",
                "packagingRequirements": ["lower_third"],
            }
        ]
    }
    updated = reconcile_gap_finish_from_storyboard(gap_report, storyboard=[], structure=structure)
    item = updated["weakSlots"][0]
    assert item["completionMode"] == "hf_native"
