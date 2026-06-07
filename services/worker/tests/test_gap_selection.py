from __future__ import annotations

import pytest

from app.pipelines.gap_selection import VideoGenQuota, select_provider, select_provider_chain


@pytest.fixture(autouse=True)
def _clear_pexels_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VIDEOMAKER_PEXELS_API_KEY", raising=False)


def _slot(
    *,
    slot_id: str = "slot-1",
    role: str = "proof",
    importance: str = "recommended",
    required: list[str] | None = None,
    script_intent: str = "",
) -> dict:
    return {
        "id": slot_id,
        "role": role,
        "importance": importance,
        "requiredAssetType": required or ["video", "image"],
        "scriptIntent": script_intent,
        "visualIntent": role,
        "startSec": 0.0,
        "endSec": 3.0,
    }


def _inventory(*, asset_id: str, asset_type: str) -> dict:
    return {
        "assets": [
            {
                "id": asset_id,
                "type": asset_type,
                "uri": f"/tmp/{asset_id}.{'mp4' if asset_type == 'video' else 'png'}",
            }
        ]
    }


def test_weak_match_image_visual_uses_video_generation() -> None:
    slot = _slot(slot_id="slot2", role="usage_scene")
    weak = {"slotId": "slot2", "assetId": "asset-img", "matchScore": 0.4}
    inv = _inventory(asset_id="asset-img", asset_type="image")
    assert (
        select_provider(
            slot,
            weak_match=weak,
            quota=VideoGenQuota(max_slots=3, max_per_slot=1),
            inventory=inv,
            variant_overrides={},
        )
        == "video_generation"
    )


def test_weak_match_video_uses_asset_reuse() -> None:
    slot = _slot(slot_id="slot2", role="usage_scene")
    weak = {"slotId": "slot2", "assetId": "asset-vid", "matchScore": 0.4}
    inv = _inventory(asset_id="asset-vid", asset_type="video")
    assert (
        select_provider(
            slot,
            weak_match=weak,
            quota=VideoGenQuota(max_slots=3, max_per_slot=1),
            inventory=inv,
            variant_overrides={},
        )
        == "asset_reuse"
    )


def test_weak_match_image_without_quota_falls_back_to_image() -> None:
    slot = _slot(slot_id="slot2", role="usage_scene")
    weak = {"slotId": "slot2", "assetId": "asset-img", "matchScore": 0.4}
    inv = _inventory(asset_id="asset-img", asset_type="image")
    quota = VideoGenQuota(max_slots=0, max_per_slot=1)
    assert (
        select_provider(
            slot,
            weak_match=weak,
            quota=quota,
            inventory=inv,
            variant_overrides={},
        )
        == "image_generation"
    )


@pytest.mark.parametrize(
    "role",
    ["hook_text", "benefit_card", "comparison"],
)
def test_select_provider_packaging_roles(role: str) -> None:
    slot = _slot(role=role, required=["text", "packaging"])
    assert (
        select_provider(
            slot,
            weak_match=None,
            quota=VideoGenQuota(max_slots=3),
            inventory={},
            variant_overrides={},
        )
        == "hyperframes_material"
    )


def test_select_provider_visual_without_weak_match_uses_video() -> None:
    slot = _slot(role="hook_visual", importance="recommended")
    assert (
        select_provider(
            slot,
            weak_match=None,
            quota=VideoGenQuota(max_slots=3, max_per_slot=1),
            inventory={},
            variant_overrides={"videoGenPriority": "high"},
            impact="medium",
        )
        == "video_generation"
    )


def test_select_provider_high_conversion_prefers_stock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIDEOMAKER_PEXELS_API_KEY", "test-key")
    slot = _slot(role="hook_visual", importance="must_have")
    overrides = {
        "preferProviders": [
            "stock_media_search",
            "hyperframes_material",
            "image_generation",
            "video_generation",
        ],
        "stockMediaPriority": "high",
        "videoGenPriority": "low",
    }
    assert (
        select_provider(
            slot,
            weak_match=None,
            quota=VideoGenQuota(max_slots=3),
            inventory={"userBrief": {"topic": "为人处世"}},
            variant_overrides=overrides,
            impact="high",
        )
        == "stock_media_search"
    )


def test_select_provider_tts_for_spoken_script() -> None:
    slot = _slot(role="proof", script_intent="需要口播解说产品卖点")
    assert (
        select_provider(
            slot,
            weak_match=None,
            quota=VideoGenQuota(max_slots=3),
            inventory={},
            variant_overrides={},
        )
        == "tts"
    )


def test_select_provider_visual_with_spoken_script_prefers_video() -> None:
    slot = _slot(role="hook_visual", script_intent="需要口播解说开场")
    assert (
        select_provider(
            slot,
            weak_match=None,
            quota=VideoGenQuota(max_slots=3, max_per_slot=1),
            inventory={},
            variant_overrides={},
        )
        == "video_generation"
    )


def test_select_provider_chain_adds_ken_burns_for_motion_image() -> None:
    slot = _slot(role="usage_scene", importance="must_have", required=["video", "image"])
    chain = select_provider_chain(
        slot,
        weak_match=None,
        quota=VideoGenQuota(max_slots=0, max_per_slot=1),
        inventory={},
        variant_overrides={},
        impact="high",
    )
    assert chain == ["image_generation", "hyperframes_material"]
