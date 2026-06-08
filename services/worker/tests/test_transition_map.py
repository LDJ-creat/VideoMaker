from __future__ import annotations

import pytest

from app.render.timeline_compiler.transition_map import (
    resolve_transition_mode,
    transition_duration_sec,
    xfade_transition_name,
)


def test_transition_duration_cut_is_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIDEOMAKER_FFMPEG_TRANSITION_MODE", "cut")
    assert resolve_transition_mode() == "cut"
    assert transition_duration_sec("fade", mode="cut") == 0.0


def test_transition_xfade_duration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIDEOMAKER_FFMPEG_TRANSITION_MODE", "xfade")
    assert transition_duration_sec("fade", mode="xfade") == 0.3
    assert xfade_transition_name("wipe") == "wiperight"
