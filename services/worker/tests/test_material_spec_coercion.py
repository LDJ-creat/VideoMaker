from __future__ import annotations

from app.validation.material_spec_coercer import coerce_material_spec_output
from app.validation.schema_loader import validate_contract


def test_coerce_material_spec_maps_template_id_and_colors() -> None:
    payload = {
        "templateId": "comparison_card",
        "durationSec": 16,
        "allowedProviders": ["hyperframes_material"],
        "assetRefs": [{"type": "image", "uri": "storage://generated/slot-2.png"}],
        "params": {
            "title": "被动附和 vs 主动接力",
            "accentColor": "#f97316",
            "backgroundColor": "#111827",
            "textColor": "#ffffff",
            "edgeFadeOpacity": 0.2,
            "overlayQuote": "多接力，少尬笑",
        },
    }
    slot = {
        "role": "comparison",
        "scriptIntent": "对比两种社交状态",
        "visualIntent": "正反对比动效卡片",
    }

    coerced = coerce_material_spec_output(payload, slot=slot)
    validation = validate_contract("material-spec", coerced)

    assert validation.valid, validation.errors
    assert coerced["template"] == "benefit-card"
    assert coerced["durationSec"] == 16
    assert coerced["params"]["colors"] == {
        "accent": "#f97316",
        "background": "#111827",
        "text": "#ffffff",
    }
    assert "edgeFadeOpacity" not in coerced["params"]
    assert coerced["params"]["assetRefs"][0]["uri"] == "storage://generated/slot-2.png"


def test_coerce_material_spec_defaults_template_from_slot_role() -> None:
    payload = {
        "templateName": "unknown-template",
        "params": {
            "primaryColor": "#2563eb",
            "zoomDirection": "in",
        },
    }
    slot = {
        "role": "hook_text",
        "scriptIntent": "是不是饭局上只会点头微笑？",
        "visualIntent": "醒目字幕",
    }

    coerced = coerce_material_spec_output(payload, slot=slot)
    validation = validate_contract("material-spec", coerced)

    assert validation.valid, validation.errors
    assert coerced["template"] == "title-lower-third"
    assert coerced["params"]["title"] == "是不是饭局上只会点头微笑？"
    assert coerced["params"]["colors"]["primary"] == "#2563eb"


def test_coerce_material_spec_downgrades_ken_burns_without_asset_refs() -> None:
    payload = {
        "template": "ken-burns",
        "durationSec": 16,
        "params": {
            "title": "被动附和 vs 主动接力",
        },
    }
    slot = {
        "role": "proof",
        "scriptIntent": "对比两种社交状态",
        "visualIntent": "正反对比动效卡片",
    }

    coerced = coerce_material_spec_output(payload, slot=slot)
    validation = validate_contract("material-spec", coerced)

    assert validation.valid, validation.errors
    assert coerced["template"] == "benefit-card"
    assert "assetRefs" not in coerced["params"]
