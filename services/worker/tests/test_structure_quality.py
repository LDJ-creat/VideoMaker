from __future__ import annotations

from app.validation.structure_quality import evaluate_structure_quality, has_critical_warnings


def test_structure_quality_flags_uniform_slots() -> None:
    structure = {
        "version": "p1-v3",
        "narrative": {
            "summary": "中文结构摘要",
            "segments": [
                {
                    "id": "seg-1",
                    "role": "hook",
                    "scriptSummary": "反问痛点",
                    "visualSummary": "胸景口播",
                    "intent": "停滑",
                    "transcriptExcerpt": "还在花冤枉钱？",
                }
            ],
        },
        "slots": [
            {"id": "s1", "role": "usage_scene", "migrationTemplate": "沿用场景镜头替换产品"},
            {"id": "s2", "role": "usage_scene", "migrationTemplate": "沿用场景镜头替换卖点"},
        ],
        "analysisQuality": {"locale": "zh"},
    }
    result = evaluate_structure_quality(structure)
    assert any("slot_roles_uniform" in item for item in result["warnings"])
    assert has_critical_warnings(result["warnings"]) is True
