from __future__ import annotations

import pytest

from composition.author.coercer import (
    build_author_fallback_spec,
    build_video_composition_fallback,
    fallback_legacy_spec,
)
from composition.author.payload import (
    VIDEO_LINT_CHECKLIST,
    build_material_author_user_payload,
    has_video_asset_refs,
)
from composition.author.react_agent import _max_turns
from composition.types import AuthorRequest


def test_max_turns_defaults_to_twelve(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VIDEOMAKER_COMPOSITION_REACT_MAX_TURNS", raising=False)
    assert _max_turns() == 12


def test_has_video_asset_refs() -> None:
    assert has_video_asset_refs([{"type": "video", "uri": "clip.mp4"}]) is True
    assert has_video_asset_refs([{"type": "image", "uri": "hero.jpg"}]) is False


def test_user_payload_includes_video_lint_checklist() -> None:
    payload = build_material_author_user_payload(
        AuthorRequest(
            slot={"role": "hook_visual"},
            asset_refs=[{"id": "base", "type": "video", "uri": "slot-1-stock.mp4"}],
        )
    )
    assert payload["videoLintChecklist"] == list(VIDEO_LINT_CHECKLIST)


def test_user_payload_omits_video_checklist_without_video() -> None:
    payload = build_material_author_user_payload(
        AuthorRequest(
            slot={"role": "benefit_card"},
            asset_refs=[{"id": "hero", "type": "image", "uri": "hero.jpg"}],
        )
    )
    assert "videoLintChecklist" not in payload


def test_build_author_fallback_spec_uses_composition_for_video() -> None:
    spec = build_author_fallback_spec(
        {
            "role": "hook_visual",
            "scriptIntent": "hook copy",
            "visualIntent": "daily scene",
        },
        asset_refs=[{"type": "video", "uri": "slot-1-stock.mp4"}],
        duration_sec=3.0,
    )
    assert spec["template"] == "composition"
    body_html = spec["composition"]["bodyHtml"]
    assert 'id="base-video"' in body_html
    assert 'data-start="0"' in body_html
    assert "slot-1-stock.mp4" in body_html
    assert "const tl" not in spec["composition"]["timelineScript"]


def test_build_author_fallback_spec_uses_ken_burns_for_image() -> None:
    spec = build_author_fallback_spec(
        {"role": "hook_visual", "scriptIntent": "hook"},
        asset_refs=[{"type": "image", "uri": "slot-stock.jpg"}],
        duration_sec=4.0,
    )
    assert spec["template"] == "ken-burns"
    assert spec["params"]["assetRefs"][0]["uri"] == "slot-stock.jpg"


def test_build_author_fallback_spec_without_assets_avoids_empty_ken_burns() -> None:
    spec = build_author_fallback_spec({"role": "hook_visual", "scriptIntent": "hook"})
    assert spec["template"] != "ken-burns"


def test_build_video_composition_fallback_requires_video_ref() -> None:
    with pytest.raises(ValueError, match="video asset ref"):
        build_video_composition_fallback({"role": "hook_visual"}, [{"type": "image", "uri": "x.jpg"}])


def test_fallback_legacy_spec_hook_visual_defaults_to_ken_burns_template_name() -> None:
    spec = fallback_legacy_spec({"role": "hook_visual", "scriptIntent": "hook"})
    assert spec["template"] == "ken-burns"
