from __future__ import annotations

from app.providers.finish_brief import build_finish_brief, build_finish_brief_for_action


def test_build_finish_brief_semantic_fields_and_voiceover_do_not_render() -> None:
    brief = build_finish_brief(
        gap_item={
            "completionMode": "source_then_polish",
            "finishIntent": "添加 lower third 与逐句字幕",
        },
        slot={
            "id": "seg-1-benefit_card-1",
            "scriptIntent": "消解受众懊悔情绪",
            "visualIntent": "三要点卡片",
            "packagingRequirements": ["lower_third", "caption"],
        },
        storyboard_scene={
            "script": "夏天出门怕晒黑？",
            "visual": "快切产品特写，自然光",
        },
        base_media={"id": "base", "type": "video", "uri": "clip.mp4"},
        packaging_plan={
            "slotOverlays": [
                {
                    "slotId": "seg-1-benefit_card-1",
                    "displayCopy": ["限时特惠"],
                }
            ]
        },
        source_provider="stock_media_search",
        duration_sec=4.5,
    )

    assert brief["creativeBrief"]["visualDirection"] == "快切产品特写，自然光"
    assert brief["creativeBrief"]["narrativeGoal"] == "消解受众懊悔情绪"
    assert "lower_third_motion" in brief["creativeBrief"]["polishTasks"]
    assert brief["voiceoverContext"]["line"] == "夏天出门怕晒黑？"
    assert brief["voiceoverContext"]["doNotRender"] is True
    assert brief["renderPolicy"]["forbidVoiceoverText"] is True
    assert brief["renderPolicy"]["forbidBriefVerbatim"] is True
    assert brief["renderPolicy"]["allowedDisplayCopy"] == ["限时特惠"]
    assert "never_render_voiceover_text" in brief["constraints"]
    assert brief["storyboardScene"]["visual"] == "快切产品特写，自然光"


def test_build_finish_brief_for_action_enriches_existing_finish_brief() -> None:
    brief = build_finish_brief_for_action(
        action={
            "slotId": "seg-hook-hook_visual-1",
            "finishBrief": {
                "completionMode": "source_then_polish",
                "finishIntent": "轻量润色",
            },
        },
        slot={
            "id": "seg-hook-hook_visual-1",
            "scriptIntent": "反问式痛点",
            "visualIntent": "手持展示",
        },
        storyboard=[
            {
                "slotId": "seg-hook-hook_visual-1",
                "script": "还在纠结选哪款？",
                "visual": "B-roll with lower third",
            }
        ],
        gap_item=None,
        base_media={"type": "video", "uri": "hook.mp4"},
        packaging_plan=None,
        source_provider="stock_media_search",
        duration_sec=3.0,
    )

    assert brief["creativeBrief"]["visualDirection"] == "B-roll with lower third"
    assert brief["voiceoverContext"]["doNotRender"] is True
    assert brief["renderPolicy"]["allowedDisplayCopy"] == []
