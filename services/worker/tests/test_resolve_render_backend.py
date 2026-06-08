from __future__ import annotations

import pytest

from app.render.resolve_render_backend import (
    build_render_backend,
    resolve_render_backend,
    timeline_requires_live_html,
)


def test_resolve_defaults_to_ffmpeg(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VIDEOMAKER_RENDER_BACKEND", raising=False)
    timeline = {"durationSec": 10, "tracks": []}
    assert resolve_render_backend(timeline) == "ffmpeg"


def test_resolve_env_ffmpeg_overrides_effect_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIDEOMAKER_RENDER_BACKEND", "ffmpeg")
    timeline = {
        "tracks": [
            {
                "id": "fx",
                "type": "effect",
                "clips": [{"id": "e1", "startSec": 0, "endSec": 1, "content": "pulse"}],
            }
        ]
    }
    assert resolve_render_backend(timeline) == "ffmpeg"


def test_timeline_effect_track_auto_fallback_to_hyperframes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("VIDEOMAKER_RENDER_BACKEND", raising=False)
    timeline = {
        "tracks": [
            {
                "id": "fx",
                "type": "effect",
                "clips": [{"id": "e1", "startSec": 0, "endSec": 1, "content": "pulse"}],
            }
        ]
    }
    assert timeline_requires_live_html(timeline) is True
    assert resolve_render_backend(timeline) == "hyperframes"


def test_build_render_backend_returns_ffmpeg_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIDEOMAKER_RENDER_BACKEND", "ffmpeg")
    from app.render.ffmpeg_backend import FfmpegRenderBackend

    backend = build_render_backend({"durationSec": 1, "tracks": []})
    assert isinstance(backend, FfmpegRenderBackend)


def test_build_render_backend_returns_hyperframes_when_forced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VIDEOMAKER_RENDER_BACKEND", "hyperframes")
    from app.render.hyperframes_backend import HyperFramesRenderBackend

    backend = build_render_backend({"durationSec": 1, "tracks": []})
    assert isinstance(backend, HyperFramesRenderBackend)
