from __future__ import annotations

import pytest

from app.pipelines.duration_target import (
    normalize_duration_target,
    recommend_duration_from_structure,
    scale_structure_to_target_duration,
)


def _sample_structure(duration_sec: float = 58.0) -> dict:
    return {
        "metadata": {"durationSec": duration_sec},
        "slots": [
            {"id": "s1", "startSec": 0.0, "endSec": duration_sec / 2},
            {"id": "s2", "startSec": duration_sec / 2, "endSec": duration_sec},
        ],
        "narrative": {
            "segments": [{"id": "seg-1", "startSec": 0.0, "endSec": duration_sec}],
        },
    }


def test_recommend_duration_from_structure_metadata() -> None:
    assert recommend_duration_from_structure(_sample_structure(58.2)) == 58.2


def test_recommend_duration_defaults_without_structure() -> None:
    assert recommend_duration_from_structure(None) == 30.0


def test_normalize_duration_target_uses_sample_when_missing() -> None:
    structure = _sample_structure(45.0)
    normalized = normalize_duration_target({}, structure)
    assert normalized["targetSec"] == 45.0
    assert normalized["recommendedSec"] == 45.0
    assert normalized["source"] == "sample"


def test_normalize_duration_target_respects_user_target() -> None:
    structure = _sample_structure(45.0)
    normalized = normalize_duration_target(
        {"durationTarget": {"targetSec": 90, "source": "user"}},
        structure,
    )
    assert normalized["targetSec"] == 90.0
    assert normalized["source"] == "user"


def test_normalize_duration_target_clamps_to_min_max() -> None:
    structure = _sample_structure(45.0)
    normalized = normalize_duration_target(
        {
            "durationTarget": {
                "targetSec": 10,
                "minSec": 20,
                "maxSec": 30,
                "source": "user",
            }
        },
        structure,
    )
    assert normalized["targetSec"] == 20.0


def test_scale_structure_to_target_duration_preserves_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VIDEOMAKER_DURATION_TARGET_MAX_SEC", "600")
    structure = _sample_structure(60.0)
    scaled = scale_structure_to_target_duration(structure, 30.0)
    assert scaled["metadata"]["durationSec"] == 30.0
    assert scaled["slots"][0]["endSec"] == pytest.approx(15.0)
    assert scaled["slots"][1]["endSec"] == pytest.approx(30.0)
    assert scaled["narrative"]["segments"][0]["endSec"] == pytest.approx(30.0)
