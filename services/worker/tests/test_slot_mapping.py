from __future__ import annotations

import json
from pathlib import Path

from app.pipelines.generation_pipeline import assemble_generation_plan, build_asset_inventory
from app.validation.schema_loader import validate_contract


def _load_slot_matches_fixture() -> list[dict]:
    fixture_path = Path(__file__).parent / "fixtures" / "agents" / "slot_mapper.json"
    return json.loads(fixture_path.read_text(encoding="utf-8"))["slotMatches"]


def test_build_asset_inventory_contract_valid() -> None:
    inventory = build_asset_inventory(
        project_id="project-1",
        user_brief={
            "topic": "便携果汁机",
            "productName": "JuiceGo",
            "sellingPoints": ["便携", "快", "易清洗"],
            "targetAudience": "上班族",
            "mustMention": ["一年质保"],
            "avoidMention": ["医疗功效"],
        },
        assets=[
            {
                "id": "asset-video-1",
                "type": "video",
                "uri": "storage://asset-video-1.mp4",
                "description": "产品使用演示",
                "tags": ["产品", "使用", "演示"],
                "durationSec": 6.0,
            }
        ],
    )
    validation = validate_contract("asset-inventory", inventory)
    assert validation.valid, validation.errors


def test_slot_mapper_fixture_has_valid_matches() -> None:
    slot_matches = _load_slot_matches_fixture()
    assert slot_matches
    probe = {
        "id": "gap-probe",
        "projectId": "project-1",
        "structureId": "structure-1",
        "inventoryId": "inventory-1",
        "slotMatches": slot_matches,
        "missingSlots": [],
        "weakSlots": [],
        "summary": "probe",
    }
    validation = validate_contract("gap-report", probe)
    assert validation.valid, validation.errors


def test_assemble_generation_plan_skips_completion_for_fully_matched_optional_slot() -> None:
    structure = {
        "id": "structure-1",
        "projectId": "project-1",
        "slots": [
            {
                "id": "slot-optional",
                "segmentId": "seg-1",
                "role": "proof",
                "startSec": 0.0,
                "endSec": 3.0,
                "requiredAssetType": ["video", "image"],
                "visualIntent": "proof",
                "scriptIntent": "proof",
                "importance": "optional",
                "constraints": [],
            }
        ],
        "packaging": {"visualDensity": "low"},
    }
    inventory = {
        "id": "inventory-1",
        "projectId": "project-1",
        "assets": [{"id": "asset-video", "type": "video", "uri": "storage://video.mp4"}],
        "extractedFacts": [{"id": "fact-1", "kind": "selling_point", "text": "x", "source": "brief"}],
    }
    slot_matches = [
        {
            "slotId": "slot-optional",
            "assetId": "asset-video",
            "matchScore": 0.85,
            "matchReason": "strong optional match",
        }
    ]
    gap_report = {
        "id": "gap-1",
        "projectId": "project-1",
        "structureId": "structure-1",
        "inventoryId": "inventory-1",
        "slotMatches": slot_matches,
        "missingSlots": [],
        "weakSlots": [],
        "summary": "optional slot matched",
    }
    storyboard = [
        {
            "id": "scene-1",
            "slotId": "slot-optional",
            "startSec": 0.0,
            "endSec": 3.0,
            "visual": "proof",
            "script": "proof",
            "source": "user_asset",
        }
    ]
    packaging_plan = {
        "styleSummary": "low density",
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
    assert plan["completionActions"] == []
