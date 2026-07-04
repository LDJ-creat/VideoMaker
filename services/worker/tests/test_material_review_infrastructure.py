from __future__ import annotations

from app.pipelines.material_review import (
    apply_infrastructure_review_waiver,
    classify_review_rejection,
)


def test_classify_infrastructure_when_sparse_base_and_black_issues() -> None:
    report = {
        "approved": False,
        "issues": ["底片不可见，预览为纯黑"],
        "suggestions": [],
    }
    diagnostics = {"maxKeyframeIntervalSec": 8.33, "reencoded": False}
    assert classify_review_rejection(report, diagnostics=diagnostics) == "infrastructure"


def test_apply_infrastructure_waiver_marks_review_unavailable() -> None:
    report = {
        "approved": False,
        "issues": ["Restore the base video as visible background"],
        "suggestions": [],
    }
    author_payload = {"baseVideoDiagnostics": {"maxKeyframeIntervalSec": 8.33, "reencoded": False}}
    merged = apply_infrastructure_review_waiver(report, author_payload=author_payload)
    assert merged["approved"] is True
    assert merged["reviewUnavailable"] is True
