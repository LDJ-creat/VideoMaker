from __future__ import annotations

from app.pipelines.gap_reconcile import (
    aigc_required,
    reconcile_provider_chain,
    reorder_by_cost_policy,
)
from app.runtime.video_gen_quota import VideoGenQuota


def _slot(**overrides) -> dict:
    base = {
        "id": "slot-hook",
        "role": "hook_visual",
        "requiredAssetType": ["video"],
        "scriptIntent": "hook",
        "visualIntent": "hook visual",
        "importance": "must_have",
    }
    base.update(overrides)
    return base


def test_reconcile_preserves_llm_chain_and_appends_finish() -> None:
    slot = _slot()
    llm_item = {
        "slotId": "slot-hook",
        "completionMode": "source_then_polish",
        "suggestedFixes": ["stock_media_search", "hyperframes_material"],
        "impact": "high",
    }
    chain, mode, notes = reconcile_provider_chain(
        llm_item=llm_item,
        slot=slot,
        weak_match=None,
        quota=VideoGenQuota(max_slots=2, max_per_slot=1),
        inventory={"userBrief": {"topic": "demo"}},
        variant_overrides={"preferProviders": ["stock_media_search", "hyperframes_material", "video_generation"]},
    )
    assert mode == "source_then_polish"
    assert chain[0] == "stock_media_search"
    assert chain[-1] == "hyperframes_material"
    assert "llm_chain_accepted" in notes


def test_product_closeup_removes_stock() -> None:
    slot = _slot(id="slot-pc", role="product_closeup")
    llm_item = {
        "slotId": "slot-pc",
        "completionMode": "source_only",
        "suggestedFixes": ["stock_media_search", "video_generation"],
        "impact": "high",
    }
    brief = {"userBrief": {"productName": "本品 X", "topic": "commerce"}}
    chain, _, notes = reconcile_provider_chain(
        llm_item=llm_item,
        slot=slot,
        weak_match=None,
        quota=VideoGenQuota(max_slots=1, max_per_slot=1),
        inventory=brief,
        variant_overrides=None,
    )
    assert "stock_media_search" not in chain
    assert "removed_stock_for_product_closeup" in notes


def test_reorder_preserves_finish_tail() -> None:
    chain = reorder_by_cost_policy(
        ["hyperframes_material", "stock_media_search"],
        variant_overrides={
            "preferProviders": [
                "stock_media_search",
                "hyperframes_material",
                "video_generation",
            ]
        },
    )
    assert chain == ["stock_media_search", "hyperframes_material"]


def test_packaging_role_source_only_keeps_hf_finish() -> None:
    slot = _slot(
        id="slot-card",
        role="benefit_card",
        requiredAssetType=["packaging"],
    )
    llm_item = {
        "slotId": "slot-card",
        "completionMode": "source_only",
        "suggestedFixes": ["stock_media_search", "hyperframes_material"],
        "impact": "high",
    }
    chain, mode, notes = reconcile_provider_chain(
        llm_item=llm_item,
        slot=slot,
        weak_match=None,
        quota=VideoGenQuota(max_slots=1, max_per_slot=1),
        inventory={"userBrief": {"topic": "demo"}},
        variant_overrides=None,
    )
    assert chain == ["stock_media_search", "hyperframes_material"]
    assert "packaging_keeps_hf_finish" in notes
    assert mode == "source_only"


def test_benefit_card_defaults_hf_native() -> None:
    slot = _slot(id="slot-card", role="benefit_card", requiredAssetType=["packaging"])
    llm_item = {
        "slotId": "slot-card",
        "suggestedFixes": ["hyperframes_material"],
        "impact": "high",
    }
    chain, mode, _ = reconcile_provider_chain(
        llm_item=llm_item,
        slot=slot,
        weak_match=None,
        quota=VideoGenQuota(),
        inventory={},
        variant_overrides=None,
    )
    assert chain == ["hyperframes_material"]
    assert mode == "hf_native"


def test_aigc_not_required_strips_video_generation() -> None:
    slot = _slot(requiredAssetType=["video"])
    llm_item = {
        "slotId": "slot-hook",
        "completionMode": "source_only",
        "suggestedFixes": ["stock_media_search", "video_generation"],
        "impact": "medium",
    }
    chain, _, notes = reconcile_provider_chain(
        llm_item=llm_item,
        slot=slot,
        weak_match=None,
        quota=VideoGenQuota(max_slots=1, max_per_slot=1),
        inventory={"userBrief": {"topic": "lifestyle"}},
        variant_overrides={"preferProviders": ["stock_media_search", "hyperframes_material", "video_generation"]},
    )
    assert "video_generation" not in chain
    assert "removed_aigc_not_required" in notes


def test_hf_native_forces_single_hyperframes() -> None:
    slot = _slot(role="benefit_card", requiredAssetType=["packaging"])
    llm_item = {
        "slotId": "slot-hook",
        "completionMode": "hf_native",
        "suggestedFixes": ["stock_media_search", "image_generation"],
        "impact": "high",
    }
    chain, mode, _ = reconcile_provider_chain(
        llm_item=llm_item,
        slot=slot,
        weak_match=None,
        quota=VideoGenQuota(),
        inventory={},
        variant_overrides=None,
    )
    assert mode == "hf_native"
    assert chain == ["hyperframes_material"]


def test_aigc_required_product_closeup() -> None:
    slot = _slot(id="slot-pc", role="product_closeup")
    assert aigc_required(
        slot,
        weak_match=None,
        inventory={"userBrief": {"productName": "本品", "contentCategory": "product_commerce"}},
    )


def test_reorder_by_cost_policy() -> None:
    chain = reorder_by_cost_policy(
        ["video_generation", "stock_media_search", "hyperframes_material"],
        variant_overrides={
            "preferProviders": [
                "stock_media_search",
                "hyperframes_material",
                "video_generation",
            ]
        },
    )
    assert chain == ["stock_media_search", "video_generation", "hyperframes_material"]
