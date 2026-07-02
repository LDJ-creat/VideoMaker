from __future__ import annotations

import pytest

from app.gateway.chat_timeout import chat_timeout_sec


def test_chat_timeout_defaults() -> None:
    assert chat_timeout_sec("text") == 120.0
    assert chat_timeout_sec("vision") == 240.0
    assert chat_timeout_sec("video_understanding") == 300.0


def test_chat_timeout_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIDEOMAKER_GATEWAY_VIDEO_UNDERSTANDING_TIMEOUT_SEC", "420")
    monkeypatch.setenv("VIDEOMAKER_GATEWAY_VISION_TIMEOUT_SEC", "180")
    monkeypatch.setenv("VIDEOMAKER_GATEWAY_CHAT_TIMEOUT_SEC", "90")
    assert chat_timeout_sec("video_understanding") == 420.0
    assert chat_timeout_sec("vision") == 180.0
    assert chat_timeout_sec("text") == 90.0
