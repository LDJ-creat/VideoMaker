from __future__ import annotations

import os

import pytest

from app.pipelines.gap_selection import select_provider
from app.runtime.video_gen_quota import VideoGenQuota
from app.stock.stock_eligibility import stock_media_eligible


def _slot(role: str = "usage_scene", script_intent: str = "展示使用场景") -> dict:
    return {
        "id": "slot-1",
        "role": role,
        "importance": "recommended",
        "requiredAssetType": ["video", "image"],
        "scriptIntent": script_intent,
    }


def test_product_closeup_not_eligible_for_commerce_brief() -> None:
    eligible, reason = stock_media_eligible(
        _slot(role="product_closeup"),
        brief={
            "contentCategory": "product_commerce",
            "productName": "SuperWidget",
            "sellingPoints": ["轻薄"],
        },
    )
    assert eligible is False
    assert reason == "product_closeup"


def test_product_closeup_eligible_for_non_product_brief() -> None:
    eligible, reason = stock_media_eligible(
        _slot(role="product_closeup", script_intent="展示社交场景示范"),
        brief={"topic": "为人处世", "sellingPoints": []},
    )
    assert eligible is True
    assert reason == "generic_visual"


def test_product_bound_script_not_eligible() -> None:
    eligible, reason = stock_media_eligible(
        _slot(script_intent="展示我们的 SuperWidget 本品特写"),
        brief={"productName": "SuperWidget", "sellingPoints": []},
    )
    assert eligible is False
    assert reason == "product_bound"


def test_usage_scene_eligible() -> None:
    eligible, reason = stock_media_eligible(_slot(), brief={"topic": "健康早餐"})
    assert eligible is True
    assert reason == "generic_visual"


def test_select_provider_uses_stock_when_pexels_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIDEOMAKER_PEXELS_API_KEY", "test-key")
    provider = select_provider(
        _slot(),
        weak_match=None,
        quota=VideoGenQuota(max_slots=1),
        inventory={"userBrief": {"topic": "kitchen", "sellingPoints": []}},
        variant_overrides={},
    )
    assert provider == "stock_media_search"


def test_select_provider_skips_stock_without_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VIDEOMAKER_PEXELS_API_KEY", raising=False)
    provider = select_provider(
        _slot(),
        weak_match=None,
        quota=VideoGenQuota(max_slots=1),
        inventory={"userBrief": {"topic": "kitchen", "sellingPoints": []}},
        variant_overrides={},
    )
    assert provider == "video_generation"


def test_select_provider_uses_stock_for_non_product_closeup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIDEOMAKER_PEXELS_API_KEY", "test-key")
    provider = select_provider(
        _slot(role="product_closeup"),
        weak_match=None,
        quota=VideoGenQuota(max_slots=0),
        inventory={"userBrief": {"topic": "为人处世", "sellingPoints": []}},
        variant_overrides={"stockMediaPriority": "high", "videoGenPriority": "low"},
    )
    assert provider == "stock_media_search"


def test_select_provider_skips_stock_for_commerce_closeup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIDEOMAKER_PEXELS_API_KEY", "test-key")
    provider = select_provider(
        _slot(role="product_closeup"),
        weak_match=None,
        quota=VideoGenQuota(max_slots=0),
        inventory={
            "userBrief": {
                "contentCategory": "product_commerce",
                "productName": "SuperWidget",
                "sellingPoints": [],
            }
        },
        variant_overrides={},
    )
    assert provider == "image_generation"
