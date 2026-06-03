from __future__ import annotations

from app.agents.packaging_designer import _assert_packaging_plan


def test_assert_packaging_plan_normalizes_llm_shape() -> None:
    payload = _assert_packaging_plan(
        {
            "packagingPlan": {
                "visualDensity": "high",
                "stickers": [{"preset": "badge"}],
                "textStyleHints": {"fontWeight": "bold"},
            }
        },
        structure={"packaging": {"visualDensity": "medium"}},
    )
    plan = payload["packagingPlan"]
    assert plan["styleSummary"]
    assert isinstance(plan["subtitle"], dict)
    assert plan["titleCards"]
    assert plan["transitions"]
