from __future__ import annotations

import json
from pathlib import Path

import pytest

from material_review_revise_context import (
    build_material_review_revise_context_payload,
    is_fork_revise_context,
    load_material_review_revise_context,
    material_review_on_revise_enabled,
    parse_material_review_revise_context,
)


def test_build_payload_respects_on_revise_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIDEOMAKER_MATERIAL_REVIEW_ENABLED", "true")
    monkeypatch.setenv("VIDEOMAKER_MATERIAL_REVIEW_ON_REVISE", "false")
    assert material_review_on_revise_enabled() is False
    assert (
        build_material_review_revise_context_payload(
            source_generation_id="gen-src",
            material_scope="scoped",
            affected_slot_ids=["slot-1"],
            affected_pipeline_stages=["generating_material", "rendering"],
        )
        == {}
    )


def test_parse_and_load_material_review_revise_context(tmp_path: Path) -> None:
    generation_root = tmp_path / "gen"
    generation_root.mkdir()
    (generation_root / "revise-context.json").write_text(
        json.dumps(
            {
                "sourceGenerationId": "gen-src",
                "materialReviewScope": "scoped",
                "materialReviewSlotIds": ["hook"],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    loaded = load_material_review_revise_context(generation_root)
    assert loaded == {
        "scope": "scoped",
        "sourceGenerationId": "gen-src",
        "affectedSlotIds": ["hook"],
    }
    assert parse_material_review_revise_context({"materialReviewScope": "all"}) == {
        "scope": "all",
        "sourceGenerationId": "",
    }


def test_is_fork_revise_context() -> None:
    assert is_fork_revise_context({"sourceGenerationId": "gen-src", "instruction": "x"}) is True
    assert is_fork_revise_context({"materialGateRevise": {"affectedSlotIds": ["slot-6"]}}) is False
    assert is_fork_revise_context({}) is False
