from __future__ import annotations

from app.pipelines.user_brief import (
    build_baseline_extracted_facts,
    infer_content_category,
    normalize_user_brief,
)


def test_normalize_user_brief_aliases_legacy_fields() -> None:
    brief = normalize_user_brief(
        {
            "productName": "便携果汁机",
            "sellingPoints": ["轻", "快"],
            "mustMention": [],
            "avoidMention": [],
        }
    )
    assert brief["subjectName"] == "便携果汁机"
    assert brief["productName"] == "便携果汁机"
    assert brief["keyPoints"] == ["轻", "快"]
    assert brief["sellingPoints"] == ["轻", "快"]
    assert brief["contentCategory"] == "product_commerce"


def test_normalize_user_brief_v2_education() -> None:
    brief = normalize_user_brief(
        {
            "contentCategory": "education",
            "topic": "天空为什么是蓝的",
            "subjectName": "瑞利散射",
            "keyPoints": ["短波散射更强"],
            "creativeGoal": "60 秒讲明白",
            "mustMention": [],
            "avoidMention": [],
        }
    )
    assert brief["contentCategory"] == "education"
    assert brief["keyPoints"] == ["短波散射更强"]
    assert brief["sellingPoints"] == ["短波散射更强"]


def test_infer_content_category_defaults_to_general() -> None:
    assert infer_content_category({"mustMention": [], "avoidMention": []}) == "general"


def test_build_baseline_extracted_facts_includes_goal_and_key_message() -> None:
    brief = normalize_user_brief(
        {
            "contentCategory": "education",
            "keyPoints": ["知识点 A"],
            "creativeGoal": "科普入门",
            "mustMention": [],
            "avoidMention": [],
        }
    )
    facts = build_baseline_extracted_facts(brief)
    kinds = {item["kind"] for item in facts}
    assert "key_message" in kinds
    assert "goal" in kinds
