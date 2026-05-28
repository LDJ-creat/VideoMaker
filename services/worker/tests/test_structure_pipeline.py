from __future__ import annotations

import json
from pathlib import Path

from app.pipelines.structure_pipeline import extract_video_structure
from app.validation.schema_loader import validate_contract


def _load_sample_analysis() -> dict:
    fixture_path = Path(__file__).parent / "fixtures" / "sample_analysis.json"
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def test_extract_video_structure_contract_valid() -> None:
    sample_analysis = _load_sample_analysis()
    structure = extract_video_structure(
        sample_analysis=sample_analysis,
        project_id="project-1",
        source_video_id="source-video-1",
    )
    validation = validate_contract("video-structure", structure)
    assert validation.valid, validation.errors


def test_extract_video_structure_uses_required_rules() -> None:
    sample_analysis = _load_sample_analysis()
    structure = extract_video_structure(
        sample_analysis=sample_analysis,
        project_id="project-1",
        source_video_id="source-video-1",
    )
    assert structure["narrative"]["segments"][0]["role"] == "hook"
    assert structure["narrative"]["segments"][-1]["role"] == "cta"
    assert structure["rhythm"]["tempo"] in {"slow", "medium", "fast", "mixed"}
    assert any(slot["role"] == "hook_visual" for slot in structure["slots"])
    assert any(slot["role"] == "cta" for slot in structure["slots"])

