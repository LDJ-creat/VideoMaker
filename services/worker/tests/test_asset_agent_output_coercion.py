from __future__ import annotations

from app.pipelines.direct_asset_understanding import coerce_asset_agent_output
from app.validation.schema_loader import validate_contract


def test_coerce_asset_agent_output_normalizes_llm_drift() -> None:
    payload = {
        "extractedFacts": [
            {
                "kind": "scene",
                "text": "饭局尬笑",
                "source": "brief",
            }
        ],
        "candidateMoments": [
            {
                "assetId": "",
                "startSec": 0,
                "endSec": 1,
                "description": "开场共鸣",
                "tags": [],
                "highlightScore": 9,
                "suggestedSegmentRoles": "hook",
            },
            {
                "startSec": 2,
                "endSec": 4,
                "description": "方案演示",
                "tags": ["solution"],
                "highlightScore": 8,
                "suggestedSegmentRoles": ["mid"],
            },
        ],
    }

    coerced = coerce_asset_agent_output(payload, asset_ids=[])
    probe = {
        "id": "inventory-probe",
        "projectId": "probe",
        "userBrief": {
            "sellingPoints": [],
            "mustMention": [],
            "avoidMention": [],
        },
        "assets": [],
        "extractedFacts": coerced["extractedFacts"],
        "candidateMoments": coerced["candidateMoments"],
    }
    validation = validate_contract("asset-inventory", probe)
    assert validation.valid, validation.errors
    assert coerced["candidateMoments"][0]["assetId"] == "brief-context"
    assert coerced["candidateMoments"][0]["highlightScore"] == 0.9
    assert coerced["candidateMoments"][0]["suggestedSegmentRoles"] == ["hook"]
    assert coerced["candidateMoments"][0]["id"]
    assert coerced["extractedFacts"][0]["id"]
