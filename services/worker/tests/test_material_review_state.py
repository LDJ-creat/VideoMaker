from __future__ import annotations

from app.pipelines.material_review_state import _slot_status_from_report


def test_slot_status_review_bypass() -> None:
    assert (
        _slot_status_from_report(
            {
                "approved": False,
                "reviewBypass": "no_in_session_marker",
                "reviewInputs": {"mode": "skipped"},
            }
        )
        == "review_bypass"
    )


def test_slot_status_review_exhausted() -> None:
    assert (
        _slot_status_from_report(
            {
                "approved": False,
                "issues": ["review_rounds_exhausted"],
            }
        )
        == "review_exhausted"
    )
