from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest

from app.agents.structure_inputs import KeyframeEncodingError, build_structure_analyst_inputs


def _fixture_analysis() -> dict:
    path = Path(__file__).parent / "fixtures" / "sample_analysis.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_build_structure_inputs_copies_core_fields() -> None:
    analysis = _fixture_analysis()
    payload = build_structure_analyst_inputs(analysis)

    assert payload["metadata"] == analysis["metadata"]
    assert payload["transcript"] == analysis["transcript"]
    assert payload["shots"] == analysis["shots"]
    assert "rhythmFacts" in payload
    assert payload["rhythmFacts"]["shotCount"] == len(analysis["shots"])


def test_rhythm_facts_tempo_mixed_for_variable_shot_lengths() -> None:
    analysis = _fixture_analysis()
    facts = build_structure_analyst_inputs(analysis)["rhythmFacts"]
    assert facts["tempoHint"] == "mixed"
    assert facts["avgShotDurationSec"] == pytest.approx(3.75, rel=0.01)


def test_keyframe_selection_one_per_shot_and_cap(tmp_path: Path) -> None:
    analysis = _fixture_analysis()
    analysis_root = tmp_path / "analysis"
    keyframes_dir = analysis_root / "keyframes"
    keyframes_dir.mkdir(parents=True)

    extra_frames = []
    for idx, shot in enumerate(analysis["shots"], start=1):
        name = f"shot-{idx}.jpg"
        (keyframes_dir / name).write_bytes(b"jpeg-bytes")
        extra_frames.append(
            {
                "shotId": f"shot-{idx}",
                "timeSec": (shot["startSec"] + shot["endSec"]) / 2,
                "path": f"keyframes/{name}",
                "score": 0.5 + idx * 0.01,
            }
        )
    analysis["keyframes"] = extra_frames

    payload = build_structure_analyst_inputs(
        analysis,
        analysis_root=analysis_root,
        max_keyframes=4,
    )
    encoded = payload["keyframes"]
    assert len(encoded) == 4
    shot_ids = {item["shotId"] for item in encoded}
    assert len(shot_ids) == len(encoded)
    for item in encoded:
        assert item["imageBase64"] == base64.b64encode(b"jpeg-bytes").decode("ascii")
        assert item["mimeType"] == "image/jpeg"


def test_keyframe_encoding_skipped_without_analysis_root() -> None:
    analysis = _fixture_analysis()
    payload = build_structure_analyst_inputs(analysis)
    assert "keyframes" not in payload or payload.get("keyframes") == []


def test_keyframe_path_outside_analysis_root_is_skipped(tmp_path: Path) -> None:
    analysis = _fixture_analysis()
    analysis_root = tmp_path / "analysis"
    analysis_root.mkdir()
    analysis["keyframes"] = [
        {"shotId": "shot-1", "timeSec": 0.5, "path": "../../escape.jpg", "score": 0.9}
    ]
    payload = build_structure_analyst_inputs(analysis, analysis_root=analysis_root)
    assert "keyframes" not in payload
    with pytest.raises(KeyframeEncodingError):
        build_structure_analyst_inputs(
            analysis,
            analysis_root=analysis_root,
            require_keyframe_files=True,
        )


def test_require_keyframe_files_raises_when_images_missing(tmp_path: Path) -> None:
    analysis = _fixture_analysis()
    analysis_root = tmp_path / "analysis"
    analysis_root.mkdir()
    with pytest.raises(KeyframeEncodingError, match="no readable image files"):
        build_structure_analyst_inputs(
            analysis,
            analysis_root=analysis_root,
            require_keyframe_files=True,
        )
