from __future__ import annotations

import json
from pathlib import Path

from app.pipelines.generation_pipeline import (
    assemble_generation_plan,
    build_asset_inventory,
    build_narration_actions,
    merge_script_subtitles_into_timeline,
)
from app.validation.schema_loader import validate_contract


def _load_structure_fixture() -> dict:
    fixture_path = Path(__file__).parent / "fixtures" / "structures" / "sample-structure.json"
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def _load_agent_fixture(name: str) -> dict:
    fixture_path = Path(__file__).parent / "fixtures" / "agents" / f"{name}.json"
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def _build_inputs() -> tuple[dict, dict]:
    structure = _load_structure_fixture()
    inventory = build_asset_inventory(
        project_id="project-1",
        user_brief={
            "topic": "便携果汁机",
            "productName": "JuiceGo",
            "sellingPoints": ["便携", "快", "易清洗"],
            "targetAudience": "上班族",
            "mustMention": ["一年质保"],
            "avoidMention": [],
        },
        assets=[
            {
                "id": "asset-text-1",
                "type": "text",
                "uri": "storage://caption-1.txt",
                "description": "核心卖点文案",
                "tags": ["文案", "卖点"],
            }
        ],
    )
    return structure, inventory


def test_gap_planner_fixture_is_contract_valid() -> None:
    report = _load_agent_fixture("gap_planner")
    validation = validate_contract("gap-report", report)
    assert validation.valid, validation.errors
    assert report["missingSlots"] or report["weakSlots"]


def test_assemble_generation_plan_and_timeline_contract_valid() -> None:
    structure, inventory = _build_inputs()
    gap_report = _load_agent_fixture("gap_planner")
    slot_matches = _load_agent_fixture("slot_mapper")["slotMatches"]
    storyboard = _load_agent_fixture("storyboard_writer")["storyboard"]
    packaging_plan = _load_agent_fixture("packaging_designer")["packagingPlan"]

    plan = assemble_generation_plan(
        structure=structure,
        inventory=inventory,
        gap_report=gap_report,
        slot_matches=slot_matches,
        storyboard=storyboard,
        packaging_plan=packaging_plan,
        variant="default",
    )
    validation = validate_contract("generation-plan", plan)
    assert validation.valid, validation.errors
    assert plan["masterNarration"]
    assert [track["type"] for track in plan["timeline"]["tracks"]] == [
        "video",
        "image",
        "text",
        "effect",
        "transition",
        "voiceover",
        "bgm",
    ]


def test_assemble_generation_plan_handles_empty_suggested_fixes() -> None:
    structure, inventory = _build_inputs()
    gap_report = _load_agent_fixture("gap_planner")
    slot_matches = _load_agent_fixture("slot_mapper")["slotMatches"]
    storyboard = _load_agent_fixture("storyboard_writer")["storyboard"]
    packaging_plan = _load_agent_fixture("packaging_designer")["packagingPlan"]

    if gap_report["missingSlots"]:
        gap_report["missingSlots"][0]["suggestedFixes"] = []
    elif gap_report["weakSlots"]:
        gap_report["weakSlots"][0]["suggestedFixes"] = []
    else:
        raise AssertionError("Expected at least one weak or missing slot")

    plan = assemble_generation_plan(
        structure=structure,
        inventory=inventory,
        gap_report=gap_report,
        slot_matches=slot_matches,
        storyboard=storyboard,
        packaging_plan=packaging_plan,
        variant="default",
    )
    assert plan["completionActions"]


def test_assemble_generation_plan_uses_asset_real_type_for_track_selection() -> None:
    structure = {
        "id": "structure-1",
        "projectId": "project-1",
        "slots": [
            {
                "id": "slot-video",
                "segmentId": "seg-1",
                "role": "usage_scene",
                "startSec": 0.0,
                "endSec": 2.0,
                "requiredAssetType": ["video", "image"],
                "visualIntent": "usage_scene",
                "scriptIntent": "usage_scene",
                "importance": "must_have",
                "constraints": [],
            },
            {
                "id": "slot-image",
                "segmentId": "seg-2",
                "role": "proof",
                "startSec": 2.0,
                "endSec": 4.0,
                "requiredAssetType": ["video", "image"],
                "visualIntent": "proof",
                "scriptIntent": "proof",
                "importance": "must_have",
                "constraints": [],
            },
        ],
        "packaging": {"visualDensity": "medium"},
    }
    inventory = {
        "id": "inventory-1",
        "projectId": "project-1",
        "assets": [
            {"id": "asset-video", "type": "video", "uri": "storage://video.mp4"},
            {"id": "asset-image", "type": "image", "uri": "storage://image.jpg"},
        ],
        "extractedFacts": [{"id": "fact-1", "kind": "selling_point", "text": "x", "source": "brief"}],
    }
    slot_matches = [
        {"slotId": "slot-video", "assetId": "asset-video", "matchScore": 0.7, "matchReason": "ok"},
        {"slotId": "slot-image", "assetId": "asset-image", "matchScore": 0.7, "matchReason": "ok"},
    ]
    gap_report = {
        "id": "gap-1",
        "projectId": "project-1",
        "structureId": "structure-1",
        "inventoryId": "inventory-1",
        "slotMatches": slot_matches,
        "missingSlots": [],
        "weakSlots": [],
        "summary": "ok",
    }
    storyboard = [
        {
            "id": "scene-1",
            "slotId": "slot-video",
            "startSec": 0.0,
            "endSec": 2.0,
            "visual": "usage_scene",
            "script": "usage_scene",
            "source": "user_asset",
        },
        {
            "id": "scene-2",
            "slotId": "slot-image",
            "startSec": 2.0,
            "endSec": 4.0,
            "visual": "proof",
            "script": "proof",
            "source": "user_asset",
        },
    ]
    packaging_plan = {
        "styleSummary": "Visual density: medium",
        "subtitle": {"preset": "clean"},
        "titleCards": [{"preset": "hook"}],
        "transitions": [{"preset": "quick-cut"}],
    }

    plan = assemble_generation_plan(
        structure=structure,
        inventory=inventory,
        gap_report=gap_report,
        slot_matches=slot_matches,
        storyboard=storyboard,
        packaging_plan=packaging_plan,
        variant="default",
    )
    video_track = next(track for track in plan["timeline"]["tracks"] if track["type"] == "video")
    image_track = next(track for track in plan["timeline"]["tracks"] if track["type"] == "image")
    assert any(clip.get("sourceRef") == "asset-video" for clip in video_track["clips"])
    assert any(clip.get("sourceRef") == "asset-image" for clip in image_track["clips"])


def test_build_narration_actions_for_scenes_with_script() -> None:
    storyboard = _load_agent_fixture("storyboard_writer")["storyboard"]
    actions = build_narration_actions(storyboard)
    scripted_scenes = [scene for scene in storyboard if str(scene.get("script", "")).strip()]
    assert len(actions) == len(scripted_scenes)
    assert all(action["provider"] == "tts" for action in actions)
    assert actions[0]["id"] == f"action-{scripted_scenes[0]['slotId']}-tts"


def test_assemble_generation_plan_includes_tts_and_subtitle_clips() -> None:
    structure, inventory = _build_inputs()
    gap_report = _load_agent_fixture("gap_planner")
    slot_matches = _load_agent_fixture("slot_mapper")["slotMatches"]
    storyboard = _load_agent_fixture("storyboard_writer")["storyboard"]
    packaging_plan = _load_agent_fixture("packaging_designer")["packagingPlan"]

    plan = assemble_generation_plan(
        structure=structure,
        inventory=inventory,
        gap_report=gap_report,
        slot_matches=slot_matches,
        storyboard=storyboard,
        packaging_plan=packaging_plan,
        variant="default",
    )

    tts_actions = [a for a in plan["completionActions"] if a.get("provider") == "tts"]
    visual_actions = [a for a in plan["completionActions"] if a.get("provider") != "tts"]
    assert tts_actions
    assert visual_actions

    text_track = next(track for track in plan["timeline"]["tracks"] if track["type"] == "text")
    scenes_with_script = [s for s in storyboard if str(s.get("script", "")).strip()]
    subtitle_clips = [c for c in text_track["clips"] if str(c.get("id", "")).startswith("subtitle-")]
    assert len(subtitle_clips) >= len(scenes_with_script)
    assert subtitle_clips[0]["styleRef"] == "style://subtitle/clean"


def test_merge_script_subtitles_respects_packaging_preset() -> None:
    timeline = {"durationSec": 5.0, "tracks": [{"id": "track-text", "type": "text", "clips": []}]}
    storyboard = [
        {
            "id": "scene-1",
            "slotId": "slot-1",
            "startSec": 0.0,
            "endSec": 5.0,
            "script": "你好世界",
        }
    ]
    updated = merge_script_subtitles_into_timeline(
        timeline,
        storyboard,
        {"subtitle": {"preset": "bold"}},
    )
    clip = updated["tracks"][0]["clips"][0]
    assert clip["id"] == "subtitle-slot-1"
    assert clip["content"] == "你好世界"
    assert clip["styleRef"] == "style://subtitle/bold"


def test_assemble_generation_plan_skips_duplicate_tts_when_gap_already_tts() -> None:
    structure = {
        "id": "structure-1",
        "projectId": "project-1",
        "slots": [
            {
                "id": "slot-proof",
                "segmentId": "seg-1",
                "role": "proof",
                "startSec": 0.0,
                "endSec": 5.0,
                "requiredAssetType": ["text"],
                "visualIntent": "proof",
                "scriptIntent": "需要口播解说",
                "importance": "must_have",
                "constraints": [],
            }
        ],
        "packaging": {"visualDensity": "medium"},
    }
    inventory = {
        "id": "inventory-1",
        "projectId": "project-1",
        "assets": [],
        "extractedFacts": [{"id": "fact-1", "kind": "selling_point", "text": "x", "source": "brief"}],
    }
    slot_matches = [{"slotId": "slot-proof", "matchScore": 0.1, "matchReason": "weak"}]
    gap_report = {
        "id": "gap-1",
        "projectId": "project-1",
        "structureId": "structure-1",
        "inventoryId": "inventory-1",
        "slotMatches": slot_matches,
        "missingSlots": [
            {
                "slotId": "slot-proof",
                "reason": "缺少口播",
                "impact": "high",
                "suggestedFixes": ["tts"],
            }
        ],
        "weakSlots": [],
        "summary": "gap",
    }
    storyboard = [
        {
            "id": "scene-1",
            "slotId": "slot-proof",
            "startSec": 0.0,
            "endSec": 5.0,
            "visual": "proof",
            "script": "这是口播稿",
            "source": "text_completion",
        }
    ]
    packaging_plan = {
        "styleSummary": "test",
        "subtitle": {"preset": "clean"},
        "titleCards": [],
        "transitions": [],
    }

    plan = assemble_generation_plan(
        structure=structure,
        inventory=inventory,
        gap_report=gap_report,
        slot_matches=slot_matches,
        storyboard=storyboard,
        packaging_plan=packaging_plan,
    )

    tts_actions = [a for a in plan["completionActions"] if a.get("provider") == "tts"]
    assert len(tts_actions) == 1
    assert tts_actions[0]["id"] == "action-slot-proof"


def test_assemble_generation_plan_expands_stock_to_ken_burns_chain() -> None:
    structure = {
        "id": "structure-1",
        "projectId": "project-1",
        "slots": [
            {
                "id": "slot-hook",
                "segmentId": "seg-1",
                "role": "hook_visual",
                "startSec": 0.0,
                "endSec": 7.0,
                "importance": "must_have",
                "requiredAssetType": ["video"],
            }
        ],
    }
    inventory = build_asset_inventory(
        project_id="project-1",
        user_brief={"topic": "饭局接话", "sellingPoints": [], "mustMention": [], "avoidMention": []},
        assets=[],
    )
    gap_report = {
        "id": "gap-1",
        "projectId": "project-1",
        "structureId": structure["id"],
        "missingSlots": [
            {
                "slotId": "slot-hook",
                "reason": "missing hook visual",
                "impact": "high",
                "suggestedFixes": ["stock_media_search", "hyperframes_material"],
            }
        ],
        "weakSlots": [],
        "summary": "1 missing",
    }
    storyboard = [
        {
            "id": "scene-hook",
            "slotId": "slot-hook",
            "startSec": 0.0,
            "endSec": 7.0,
            "visual": "饭局尬笑",
            "script": "你是不是只会点头微笑？",
            "source": "generated",
        }
    ]
    plan = assemble_generation_plan(
        structure=structure,
        inventory=inventory,
        gap_report=gap_report,
        slot_matches=[],
        storyboard=storyboard,
        packaging_plan={"styleSummary": "demo", "subtitle": {"preset": "clean"}, "titleCards": [], "transitions": []},
        generation_strategy="long_form_composed",
    )
    visual_actions = [
        action
        for action in plan["completionActions"]
        if action.get("provider") != "tts"
    ]
    assert [action["id"] for action in visual_actions] == [
        "action-slot-hook",
        "action-slot-hook-ken-burns",
    ]


def test_build_narration_actions_global_mode() -> None:
    actions = build_narration_actions(
        [{"slotId": "slot-1", "script": "分镜文案"}],
        master_narration="全片口播全文。",
        tts_mode="global",
    )
    assert len(actions) == 1
    assert actions[0]["id"] == "action-master-tts"
    assert actions[0]["slotId"] == "__master__"


def test_assemble_generation_plan_long_form_uses_global_tts() -> None:
    structure, inventory = _build_inputs()
    gap_report = _load_agent_fixture("gap_planner")
    slot_matches = _load_agent_fixture("slot_mapper")["slotMatches"]
    storyboard = _load_agent_fixture("storyboard_writer")["storyboard"]
    packaging_plan = _load_agent_fixture("packaging_designer")["packagingPlan"]

    plan = assemble_generation_plan(
        structure=structure,
        inventory=inventory,
        gap_report=gap_report,
        slot_matches=slot_matches,
        storyboard=storyboard,
        packaging_plan=packaging_plan,
        variant="default",
        generation_strategy="long_form_composed",
        master_narration="全片口播示例文案。",
    )
    assert plan.get("ttsMode") == "global"
    tts_actions = [a for a in plan["completionActions"] if a.get("provider") == "tts"]
    assert len(tts_actions) == 1
    assert tts_actions[0]["slotId"] == "__master__"
    text_track = next(track for track in plan["timeline"]["tracks"] if track["type"] == "text")
    assert not any(str(c.get("id", "")).startswith("subtitle-") for c in text_track["clips"])
