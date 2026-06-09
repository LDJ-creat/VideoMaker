from __future__ import annotations

from pathlib import Path

import pytest

from composition.patterns.deposit import (
    composition_draft_dir,
    composition_pattern_entry_id,
    promote_pattern,
)
from composition.types import PatternPromoteRequest
from knowledge.paths import validate_storage_segment


def test_validate_storage_segment_rejects_traversal() -> None:
    with pytest.raises(ValueError, match="invalid_slot_id"):
        validate_storage_segment("../evil", field="slot_id")
    with pytest.raises(ValueError, match="invalid_generation_id"):
        validate_storage_segment("gen/evil", field="generation_id")


def test_composition_draft_dir_stays_under_project(tmp_path: Path) -> None:
    storage = tmp_path / "storage"
    storage.mkdir()
    path = composition_draft_dir(
        storage,
        project_id="proj-1",
        generation_id="gen-1",
        slot_id="slot-1",
    )
    assert path.resolve().is_relative_to(storage.resolve())


def test_composition_pattern_entry_id_rejects_unsafe_slot() -> None:
    with pytest.raises(ValueError, match="invalid_slot_id"):
        composition_pattern_entry_id("gen-1", "../../secrets")


def test_promote_pattern_rejects_unsafe_ids(tmp_path: Path) -> None:
    storage = tmp_path / "storage"
    storage.mkdir()
    with pytest.raises(ValueError, match="invalid_generation_id"):
        promote_pattern(
            PatternPromoteRequest(
                storage_root=storage,
                project_id="proj-1",
                generation_id="../evil",
                slot_id="slot-1",
            ),
        )
