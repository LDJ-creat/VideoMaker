from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient


def _clear_gateway_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "TEXT_API_BASE",
        "TEXT_API_KEY",
        "TEXT_MODEL",
        "VISION_API_BASE",
        "VISION_API_KEY",
        "VISION_MODEL",
        "TTS_API_BASE",
        "TTS_API_KEY",
        "TTS_MODEL",
        "IMAGE_API_BASE",
        "IMAGE_API_KEY",
        "IMAGE_MODEL",
        "VIDEO_API_BASE",
        "VIDEO_API_KEY",
        "VIDEO_MODEL",
        "VIDEO_DRIVER",
        "VIDEOMAKER_FIXTURE_MODE",
    ):
        monkeypatch.delenv(name, raising=False)


def test_model_gateway_status_returns_provider_shape(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_gateway_env(monkeypatch)
    monkeypatch.setenv("TEXT_API_KEY", "text-secret")
    monkeypatch.setenv("TEXT_MODEL", "gpt-4o")
    monkeypatch.setenv("IMAGE_API_KEY", "image-secret")
    monkeypatch.setenv("IMAGE_MODEL", "dall-e-3")

    response = client.get("/api/settings/model-gateway")

    assert response.status_code == 200
    payload = response.json()
    assert payload["fixtureMode"] is False
    assert payload["providers"]["text"] == {
        "configured": True,
        "model": "gpt-4o",
        "driver": "openai_compatible",
    }
    assert payload["providers"]["vision"] == {
        "configured": True,
        "model": "gpt-4o",
        "driver": "openai_compatible",
    }
    assert payload["providers"]["tts"] == {
        "configured": False,
        "model": None,
        "driver": "openai_compatible",
    }
    assert payload["providers"]["image"] == {
        "configured": True,
        "model": "dall-e-3",
        "driver": "openai_compatible",
    }
    assert payload["providers"]["video"] == {
        "configured": False,
        "model": None,
        "driver": "generic_job",
    }


def test_model_gateway_status_vision_uses_text_fallback_model(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_gateway_env(monkeypatch)
    monkeypatch.setenv("TEXT_API_KEY", "text-secret")
    monkeypatch.setenv("TEXT_MODEL", "text-model")
    monkeypatch.setenv("VISION_API_KEY", "vision-secret")
    monkeypatch.setenv("VISION_MODEL", "vision-model")

    response = client.get("/api/settings/model-gateway")

    assert response.status_code == 200
    assert response.json()["providers"]["vision"] == {
        "configured": True,
        "model": "vision-model",
        "driver": "openai_compatible",
    }


def test_model_gateway_status_reports_fixture_mode(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_gateway_env(monkeypatch)
    monkeypatch.setenv("VIDEOMAKER_FIXTURE_MODE", "true")

    response = client.get("/api/settings/model-gateway")

    assert response.status_code == 200
    assert response.json()["fixtureMode"] is True


def test_model_gateway_status_never_exposes_secrets(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_gateway_env(monkeypatch)
    monkeypatch.setenv("TEXT_API_KEY", "super-secret-text-key")
    monkeypatch.setenv("VISION_API_KEY", "super-secret-vision-key")
    monkeypatch.setenv("TTS_API_KEY", "super-secret-tts-key")
    monkeypatch.setenv("IMAGE_API_KEY", "super-secret-image-key")
    monkeypatch.setenv("VIDEO_API_KEY", "super-secret-video-key")
    monkeypatch.setenv("VIDEO_API_BASE", "https://video.example/v1")

    response = client.get("/api/settings/model-gateway")
    raw = json.dumps(response.json())

    assert response.status_code == 200
    assert "api_key" not in raw
    assert "apiKey" not in raw
    assert "super-secret" not in raw


def test_model_gateway_status_video_configured_with_base_url(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _clear_gateway_env(monkeypatch)
    monkeypatch.setenv("VIDEO_API_BASE", "https://video.example/v1")
    monkeypatch.setenv("VIDEO_MODEL", "video-model")
    monkeypatch.setenv("VIDEO_DRIVER", "generic_job")

    response = client.get("/api/settings/model-gateway")

    assert response.status_code == 200
    assert response.json()["providers"]["video"] == {
        "configured": True,
        "model": "video-model",
        "driver": "generic_job",
    }
