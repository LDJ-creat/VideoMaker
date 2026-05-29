from __future__ import annotations

import json
from pathlib import Path

from app.pipelines.generation_pipeline import assemble_generation_plan, build_asset_inventory
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
