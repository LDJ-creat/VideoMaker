from __future__ import annotations

import pytest

from app.pipelines.gap_selection import VideoGenQuota, select_provider, select_provider_chain


def _slot(
    *,
    role: str = "proof",
    importance: str = "recommended",
    required: list[str] | None = None,
    script_intent: str = "",
) -> dict:
    return {
        "id": "slot-1",
        "role": role,
        "importance": importance,
        "requiredAssetType": required or ["video", "image"],
        "scriptIntent": script_intent,
        "visualIntent": role,
        "startSec": 0.0,
        "endSec": 3.0,
    }


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (0.4, "asset_reuse"),
        (0.38, "asset_reuse"),
    ],
)
def test_select_provider_weak_match_asset_reuse(score: float, expected: str) -> None:
    slot = _slot(role="usage_scene")
    weak = {"slotId": "slot-1", "matchScore": score, "matchReason": "弱匹配"}
    assert (
        select_provider(slot, weak_match=weak, quota=VideoGenQuota(remaining=1), variant_overrides={})
        == expected
    )


def test_select_provider_weak_match_below_threshold_uses_visual_rules() -> None:
    slot = _slot(role="hook_text", required=["text", "packaging"])
    weak = {"slotId": "slot-1", "matchScore": 0.2, "matchReason": "差"}
    assert (
        select_provider(slot, weak_match=weak, quota=VideoGenQuota(remaining=1), variant_overrides={})
        == "hyperframes_material"
    )


@pytest.mark.parametrize(
    "role",
    ["hook_text", "benefit_card", "comparison"],
)
def test_select_provider_packaging_roles(role: str) -> None:
    slot = _slot(role=role, required=["text", "packaging"])
    assert (
        select_provider(slot, weak_match=None, quota=VideoGenQuota(remaining=1), variant_overrides={})
        == "hyperframes_material"
    )


def test_select_provider_required_packaging_type() -> None:
    slot = _slot(role="proof", required=["packaging", "text"])
    assert (
        select_provider(slot, weak_match=None, quota=VideoGenQuota(remaining=1), variant_overrides={})
        == "hyperframes_material"
    )


def test_select_provider_video_generation_when_quota_and_must_have_high() -> None:
    slot = _slot(role="hook_visual", importance="must_have")
    quota = VideoGenQuota(remaining=1)
    provider = select_provider(
        slot,
        weak_match=None,
        quota=quota,
        variant_overrides={"videoGenPriority": "high"},
        impact="high",
    )
    assert provider == "video_generation"
    assert quota.remaining == 0


def test_select_provider_image_when_quota_exhausted() -> None:
    slot = _slot(role="product_closeup", importance="must_have")
    assert (
        select_provider(
            slot,
            weak_match=None,
            quota=VideoGenQuota(remaining=0),
            variant_overrides={},
            impact="high",
        )
        == "image_generation"
    )


def test_select_provider_image_when_impact_not_high() -> None:
    slot = _slot(role="hook_visual", importance="must_have")
    assert (
        select_provider(
            slot,
            weak_match=None,
            quota=VideoGenQuota(remaining=1),
            variant_overrides={},
            impact="medium",
        )
        == "image_generation"
    )


def test_select_provider_high_conversion_skips_video_even_with_quota() -> None:
    slot = _slot(role="hook_visual", importance="must_have")
    overrides = {
        "preferProviders": ["hyperframes_material", "image_generation"],
        "videoGenPriority": "low",
    }
    assert (
        select_provider(
            slot,
            weak_match=None,
            quota=VideoGenQuota(remaining=1),
            variant_overrides=overrides,
            impact="high",
        )
        == "image_generation"
    )


def test_select_provider_tts_for_spoken_script() -> None:
    slot = _slot(role="proof", script_intent="需要口播解说产品卖点")
    assert (
        select_provider(slot, weak_match=None, quota=VideoGenQuota(remaining=1), variant_overrides={})
        == "tts"
    )


def test_select_provider_default_hyperframes() -> None:
    slot = _slot(role="proof", script_intent="展示对比")
    assert (
        select_provider(slot, weak_match=None, quota=VideoGenQuota(remaining=1), variant_overrides={})
        == "hyperframes_material"
    )


def test_select_provider_chain_adds_ken_burns_for_motion_image() -> None:
    slot = _slot(role="usage_scene", importance="must_have", required=["video", "image"])
    chain = select_provider_chain(
        slot,
        weak_match=None,
        quota=VideoGenQuota(remaining=0),
        variant_overrides={},
        impact="high",
    )
    assert chain == ["image_generation", "hyperframes_material"]


def test_video_gen_quota_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIDEOMAKER_VIDEO_GEN_QUOTA", "2")
    quota = VideoGenQuota.from_env()
    assert quota.remaining == 2
