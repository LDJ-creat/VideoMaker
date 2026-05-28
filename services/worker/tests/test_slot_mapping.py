from __future__ import annotations

import json
from pathlib import Path

from app.pipelines.generation_pipeline import build_asset_inventory, build_gap_report, map_slots
from app.pipelines.structure_pipeline import extract_video_structure
from app.validation.schema_loader import validate_contract


def _load_sample_analysis() -> dict:
    fixture_path = Path(__file__).parent / "fixtures" / "sample_analysis.json"
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def test_build_asset_inventory_contract_valid() -> None:
    inventory = build_asset_inventory(
        project_id="project-1",
        user_brief={
            "topic": "便携果汁机",
            "productName": "JuiceGo",
            "sellingPoints": ["便携", "快", "易清洗"],
            "targetAudience": "上班族",
            "mustMention": ["一年质保"],
            "avoidMention": ["医疗功效"]
        },
        assets=[
            {
                "id": "asset-video-1",
                "type": "video",
                "uri": "storage://asset-video-1.mp4",
                "description": "产品使用演示",
                "tags": ["产品", "使用", "演示"],
                "durationSec": 6.0
            }
        ],
    )
    validation = validate_contract("asset-inventory", inventory)
    assert validation.valid, validation.errors


def test_map_slots_prefers_semantic_and_type_match() -> None:
    structure = extract_video_structure(
        sample_analysis=_load_sample_analysis(),
        project_id="project-1",
        source_video_id="source-video-1",
    )
    inventory = build_asset_inventory(
        project_id="project-1",
        user_brief={
            "topic": "便携果汁机",
            "productName": "JuiceGo",
            "sellingPoints": ["便携", "快", "易清洗"],
            "targetAudience": "上班族",
            "mustMention": ["一年质保"],
            "avoidMention": []
        },
        assets=[
            {
                "id": "video-good",
                "type": "video",
                "uri": "storage://video-good.mp4",
                "description": "真实产品使用场景，效率提升",
                "tags": ["真实", "使用", "效率", "提升"],
                "durationSec": 8.0
            },
            {
                "id": "image-1",
                "type": "image",
                "uri": "storage://image-1.jpg",
                "description": "产品静态图",
                "tags": ["产品"]
            }
        ],
    )
    mapping = map_slots(structure=structure, inventory=inventory)
    assert mapping.slot_matches
    assert any(match["matchScore"] >= 0.62 for match in mapping.slot_matches)


def test_optional_slot_can_be_matched_with_scaled_threshold() -> None:
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
        "assets": [{"id": "asset-video", "type": "video", "uri": "storage://video.mp4", "durationSec": 4.0}],
        "extractedFacts": [{"id": "fact-1", "kind": "selling_point", "text": "x", "source": "brief"}],
    }
    slot_matches = [
        {
            "slotId": "slot-optional",
            "assetId": "asset-video",
            "matchScore": 0.45,
            "matchReason": "perfect optional score ceiling",
        }
    ]
    report = build_gap_report(structure=structure, inventory=inventory, slot_matches=slot_matches)
    assert report["missingSlots"] == []
    assert report["weakSlots"] == []

