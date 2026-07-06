from __future__ import annotations

from app.pipelines.composition_validator import (
    validate_material_spec_duration,
    validate_storyboard_timing_consistency,
)


def test_validate_storyboard_timing_consistency_flags_tail_drift() -> None:
    errors = validate_storyboard_timing_consistency(
        storyboard=[
            {"slotId": "a", "startSec": 0.0, "endSec": 3.0},
            {"slotId": "b", "startSec": 3.0, "endSec": 5.0},
        ],
        narration_duration_sec=6.0,
    )
    assert errors


def test_validate_material_spec_duration_blocks_oversized_spec() -> None:
    errors = validate_material_spec_duration(
        spec={"durationSec": 6.0},
        slot_timing={"durationSec": 4.0},
    )
    assert errors
