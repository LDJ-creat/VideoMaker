from __future__ import annotations

import pytest

from app.pipelines.composition_brief import (
    apply_composition_briefs_to_storyboard,
    gap_item_for_slot,
    infer_composition_brief_mode,
    merge_display_copy_from_packaging,
    normalize_composition_author_brief,
    scene_requires_composition_author_brief,
)


def test_scene_requires_brief_for_packaging_completion() -> None:
    assert scene_requires_composition_author_brief(
        scene={"source": "packaging_completion"},
        slot={"role": "usage_scene"},
        gap_item=None,
    )


def test_scene_requires_brief_for_hyperframes_in_gap() -> None:
    assert scene_requires_composition_author_brief(
        scene={"source": "generated"},
        slot={"role": "hook_visual"},
        gap_item={
            "completionMode": "source_then_polish",
            "suggestedFixes": ["stock_media_search", "hyperframes_material"],
        },
    )


def test_infer_mode_source_then_polish() -> None:
    mode = infer_composition_brief_mode(
        scene={"source": "generated"},
        slot={"role": "hook_visual"},
        gap_item={
            "completionMode": "source_then_polish",
            "suggestedFixes": ["asset_reuse", "hyperframes_material"],
        },
    )
    assert mode == "source_then_polish"


def test_infer_mode_hf_only_cta_coerces_to_hf_native() -> None:
    mode = infer_composition_brief_mode(
        scene={"source": "generated"},
        slot={"role": "cta"},
        gap_item={
            "completionMode": "source_then_polish",
            "suggestedFixes": ["hyperframes_material"],
        },
    )
    assert mode == "hf_native"


def test_normalize_composition_author_brief_coerces_template() -> None:
    brief = normalize_composition_author_brief(
        {
            "mode": "hf_native",
            "authorPrompt": "竖屏卖点卡：三行利益点，无口播文字，动效从下到上揭示。",
        },
        scene={"source": "packaging_completion"},
        slot={"role": "benefit_card"},
        gap_item=None,
    )
    assert brief is not None
    assert brief["templatePreference"] == "benefit-card"
    assert brief["layoutAnchor"] == "center"
    assert "垂直水平居中" in brief["authorPrompt"] or "居中" in brief["authorPrompt"]


def test_normalize_hf_native_realigns_lower_third_anchor() -> None:
    brief = normalize_composition_author_brief(
        {
            "mode": "hf_native",
            "layoutAnchor": "lower_third",
            "authorPrompt": "对比条贴底展示卖点。",
        },
        scene={"source": "packaging_completion"},
        slot={"role": "benefit_card"},
        gap_item=None,
    )
    assert brief is not None
    assert brief["layoutAnchor"] == "center"


def test_infer_layout_anchor_polish_cta() -> None:
    from app.pipelines.composition_brief import infer_layout_anchor

    assert (
        infer_layout_anchor(mode="source_then_polish", slot={"role": "cta"})
        == "lower_third"
    )
    assert infer_layout_anchor(mode="hf_native", slot={"role": "cta"}) == "center"


def test_apply_storyboard_briefs_require_mode_raises() -> None:
    structure = {
        "slots": [
            {
                "id": "slot-card",
                "role": "benefit_card",
                "packagingRequirements": ["lower_third"],
            }
        ]
    }
    storyboard = [
        {
            "id": "scene-slot-card",
            "slotId": "slot-card",
            "startSec": 0.0,
            "endSec": 3.0,
            "visual": "卖点卡",
            "script": "第一句。",
            "source": "packaging_completion",
        }
    ]
    with pytest.raises(ValueError, match="compositionAuthorBrief required"):
        apply_composition_briefs_to_storyboard(
            storyboard,
            structure=structure,
            gap_report={},
        )


def test_merge_display_copy_from_packaging() -> None:
    brief = merge_display_copy_from_packaging(
        {
            "mode": "hf_native",
            "authorPrompt": "CTA lower third",
            "displayCopyPolicy": {"allowed": ["限时特惠"]},
        },
        {"displayCopy": ["立即购买", "限时特惠"]},
    )
    assert brief["displayCopyPolicy"]["allowed"] == ["限时特惠", "立即购买"]


def test_apply_storyboard_realigns_mode_after_gap_change() -> None:
    structure = {
        "slots": [
            {
                "id": "slot-hook",
                "role": "hook_visual",
                "startSec": 0.0,
                "endSec": 3.0,
            }
        ]
    }
    storyboard = [
        {
            "id": "scene-slot-hook",
            "slotId": "slot-hook",
            "startSec": 0.0,
            "endSec": 3.0,
            "visual": "B-roll",
            "script": "第一句。",
            "source": "generated",
            "compositionAuthorBrief": {
                "mode": "hf_native",
                "authorPrompt": "保留 B-roll，轻量 lower third 润色，无口播文字。",
            },
        }
    ]
    gap_report = {
        "weakSlots": [
            {
                "slotId": "slot-hook",
                "completionMode": "source_then_polish",
                "suggestedFixes": ["stock_media_search", "hyperframes_material"],
            }
        ],
        "missingSlots": [],
    }
    warnings: list[str] = []
    updated = apply_composition_briefs_to_storyboard(
        storyboard,
        structure=structure,
        gap_report=gap_report,
        emit_warning=warnings.append,
    )
    assert updated[0]["compositionAuthorBrief"]["mode"] == "source_then_polish"
    assert warnings


def test_report_composition_brief_warnings_emits_dedicated_stage() -> None:
    from app.pipelines.composition_brief import report_composition_brief_warnings

    events: list[tuple[str, str]] = []

    def emit_event(*, stage: str, progress: int, message: str) -> None:
        events.append((stage, message))

    report_composition_brief_warnings(
        ["compositionAuthorBrief required for slot slot-1"],
        emit_event=emit_event,
    )
    assert events == [("composition_brief_warning", "compositionAuthorBrief required for slot slot-1")]


def test_gap_item_for_slot_reads_weak_slots() -> None:
    gap = {
        "weakSlots": [{"slotId": "slot-1", "completionMode": "hf_native"}],
        "missingSlots": [],
    }
    item = gap_item_for_slot(gap, "slot-1")
    assert item is not None
    assert item["completionMode"] == "hf_native"
