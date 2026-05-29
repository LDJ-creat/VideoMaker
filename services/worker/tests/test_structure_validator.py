from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.validation.structure_validator import (
    StructureValidationError,
    validate_video_structure,
)


def _valid_structure() -> dict:
    path = Path(__file__).parent / "fixtures" / "agents" / "structure_analyst.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_validate_accepts_fixture_structure() -> None:
    structure = _valid_structure()
    assert validate_video_structure(structure) == structure


def test_validate_requires_evidence_per_segment() -> None:
    structure = _valid_structure()
    structure["evidence"] = [
        item for item in structure["evidence"] if not item["targetId"].startswith("seg-2")
    ]
    with pytest.raises(StructureValidationError, match="segment evidence"):
        validate_video_structure(structure)


def test_validate_requires_valid_slot_segment_ids() -> None:
    structure = _valid_structure()
    structure["slots"][0]["segmentId"] = "missing-segment"
    with pytest.raises(StructureValidationError, match="slot segmentId"):
        validate_video_structure(structure)


def test_validate_rejects_confidence_out_of_range() -> None:
    structure = _valid_structure()
    structure["confidence"] = 1.5
    with pytest.raises(StructureValidationError, match="confidence"):
        validate_video_structure(structure)


def test_validate_cta_must_end_near_video_end() -> None:
    structure = _valid_structure()
    for segment in structure["narrative"]["segments"]:
        if segment["role"] == "cta":
            segment["endSec"] = 10.0
    with pytest.raises(StructureValidationError, match="cta"):
        validate_video_structure(structure)


def test_validate_rejects_asr_evidence_without_time_range() -> None:
    structure = _valid_structure()
    structure["evidence"] = [
        item
        for item in structure["evidence"]
        if item["targetId"] != "seg-hook"
    ]
    structure["evidence"].append(
        {
            "targetId": "seg-hook",
            "source": "asr",
            "summary": "hook text without timestamps",
            "confidence": 0.5,
        }
    )
    with pytest.raises(StructureValidationError, match="segment evidence"):
        validate_video_structure(structure)


def test_validate_rhythm_shot_boundaries_align_with_reference_shots() -> None:
    import json

    analysis_path = Path(__file__).parent / "fixtures" / "sample_analysis.json"
    shots = json.loads(analysis_path.read_text(encoding="utf-8"))["shots"]
    structure = _valid_structure()
    validate_video_structure(structure, reference_shots=shots)


def test_validate_rhythm_misaligned_shot_boundaries_fail() -> None:
    import json

    analysis_path = Path(__file__).parent / "fixtures" / "sample_analysis.json"
    shots = json.loads(analysis_path.read_text(encoding="utf-8"))["shots"]
    structure = _valid_structure()
    structure["rhythm"]["shotBoundaries"][0]["startSec"] = 99.0
    with pytest.raises(StructureValidationError, match="rhythm.shotBoundaries"):
        validate_video_structure(structure, reference_shots=shots)
