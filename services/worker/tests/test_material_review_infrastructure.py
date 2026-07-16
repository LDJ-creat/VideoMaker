from __future__ import annotations

import pytest

from app.pipelines.material_review import (
    apply_infrastructure_review_waiver,
    classify_review_rejection,
    material_review_max_rounds,
)
from app.validation.schema_loader import validate_contract


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


def test_infrastructure_waiver_report_matches_material_review_schema() -> None:
    report = {
        "slotId": "slot-1",
        "generationId": "gen-1",
        "reviewedAt": "2026-07-05T06:41:00Z",
        "approved": False,
        "issues": ["Restore the base video as visible background"],
        "suggestions": [],
        "reviewInputs": {"mode": "video"},
        "trace": {"reviewRoute": "video"},
    }
    merged = apply_infrastructure_review_waiver(
        report,
        author_payload={"baseVideoDiagnostics": {"maxKeyframeIntervalSec": 8.33, "reencoded": False}},
    )
    validation = validate_contract("material-review-report", merged)
    assert validation.valid, validation.errors


def test_material_review_max_rounds_default_and_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VIDEOMAKER_MATERIAL_REVIEW_MAX_ROUNDS", raising=False)
    assert material_review_max_rounds() == 1
    monkeypatch.setenv("VIDEOMAKER_MATERIAL_REVIEW_MAX_ROUNDS", "3")
    assert material_review_max_rounds() == 3
