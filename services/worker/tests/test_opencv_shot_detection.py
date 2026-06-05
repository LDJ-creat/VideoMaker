from __future__ import annotations

from app.tools.opencv_tool import (
    env_min_shot_duration_sec,
    should_relax_fast_cut_shot_detection,
)


def test_env_min_shot_duration_sec_reads_override(monkeypatch) -> None:
    monkeypatch.setenv("VIDEOMAKER_MIN_SHOT_DURATION_SEC", "1.2")
    assert env_min_shot_duration_sec() == 1.2


def test_should_relax_fast_cut_when_many_shots_per_second(monkeypatch) -> None:
    monkeypatch.delenv("VIDEOMAKER_MIN_SHOT_DURATION_SEC", raising=False)
    shots = [{"startSec": float(index), "endSec": float(index + 1)} for index in range(60)]
    assert should_relax_fast_cut_shot_detection(shots, 120.0) is True


def test_should_not_relax_when_env_override_set(monkeypatch) -> None:
    monkeypatch.setenv("VIDEOMAKER_MIN_SHOT_DURATION_SEC", "0.45")
    shots = [{"startSec": float(index), "endSec": float(index + 1)} for index in range(60)]
    assert should_relax_fast_cut_shot_detection(shots, 120.0) is False
