from __future__ import annotations

from app.pipelines.gap_reconcile import coerce_finish_intent_for_mode


def test_coerce_hf_native_strips_lower_third_intent() -> None:
    intent = coerce_finish_intent_for_mode(
        completion_mode="hf_native",
        slot={"role": "benefit_card"},
        finish_intent="强化卖点字卡与对比条，突出核心利益点",
    )
    assert intent is not None
    assert "居中" in intent
    assert "对比条" not in intent
    assert intent.startswith("竖屏居中")


def test_coerce_source_then_polish_keeps_lower_third_cta() -> None:
    intent = coerce_finish_intent_for_mode(
        completion_mode="source_then_polish",
        slot={"role": "cta"},
        finish_intent="明确行动号召 lower third，动词清晰",
    )
    assert intent == "明确行动号召 lower third，动词清晰"


def test_coerce_hf_native_default_when_missing() -> None:
    intent = coerce_finish_intent_for_mode(
        completion_mode="hf_native",
        slot={"role": "proof"},
        finish_intent=None,
    )
    assert intent is not None
    assert "居中" in intent
