from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient


def _live_fixture_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIDEOMAKER_FIXTURE_MODE", "false")


def _put_text_and_image(client: TestClient) -> None:
    response = client.put(
        "/api/settings/model-gateway",
        json={
            "providers": {
                "text": {
                    "baseUrl": "https://api.openai.com/v1",
                    "apiKey": "text-secret",
                    "model": "gpt-4o",
                },
                "image": {
                    "baseUrl": "https://api.openai.com/v1",
                    "apiKey": "image-secret",
                    "model": "dall-e-3",
                },
            }
        },
    )
    assert response.status_code == 200


def test_model_gateway_status_returns_provider_shape(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _live_fixture_env(monkeypatch)
    _put_text_and_image(client)

    response = client.get("/api/settings/model-gateway")

    assert response.status_code == 200
    payload = response.json()
    assert payload["fixtureMode"] is False
    assert payload["providers"]["text"]["configured"] is True
    assert payload["providers"]["text"]["model"] == "gpt-4o"
    assert payload["providers"]["text"]["hasApiKey"] is True
    assert payload["providers"]["text"]["driver"] == "openai_compatible"
    assert payload["providers"]["vision"]["configured"] is True
    assert payload["providers"]["vision"]["model"] == "gpt-4o-mini"
    assert payload["providers"]["tts"]["configured"] is False
    assert payload["providers"]["tts"]["model"] is None
    assert payload["providers"]["image"]["configured"] is True
    assert payload["providers"]["image"]["model"] == "dall-e-3"
    assert payload["providers"]["video"]["configured"] is False
    assert payload["providers"]["video"]["model"] is None
    assert payload["providers"]["video"]["driver"] == "generic_job"


def test_model_gateway_status_vision_uses_text_fallback_model(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _live_fixture_env(monkeypatch)
    client.put(
        "/api/settings/model-gateway",
        json={
            "providers": {
                "text": {"apiKey": "text-secret", "model": "text-model"},
                "vision": {"apiKey": "vision-secret", "model": "vision-model"},
            }
        },
    )

    response = client.get("/api/settings/model-gateway")

    assert response.status_code == 200
    assert response.json()["providers"]["vision"]["model"] == "vision-model"
    assert response.json()["providers"]["vision"]["configured"] is True


def test_model_gateway_status_reports_fixture_mode(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VIDEOMAKER_FIXTURE_MODE", "true")

    response = client.get("/api/settings/model-gateway")

    assert response.status_code == 200
    assert response.json()["fixtureMode"] is True


def test_model_gateway_status_never_exposes_secrets(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _live_fixture_env(monkeypatch)
    client.put(
        "/api/settings/model-gateway",
        json={
            "providers": {
                "text": {"apiKey": "super-secret-text-key", "model": "m1"},
                "vision": {"apiKey": "super-secret-vision-key", "model": "m2"},
                "tts": {"apiKey": "super-secret-tts-key", "model": "m3"},
                "image": {"apiKey": "super-secret-image-key", "model": "m4"},
                "video": {
                    "baseUrl": "https://video.example/v1",
                    "apiKey": "super-secret-video-key",
                    "model": "m5",
                },
            }
        },
    )

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
    _live_fixture_env(monkeypatch)
    client.put(
        "/api/settings/model-gateway",
        json={
            "providers": {
                "video": {
                    "baseUrl": "https://video.example/v1",
                    "model": "video-model",
                    "driver": "generic_job",
                }
            }
        },
    )

    response = client.get("/api/settings/model-gateway")

    assert response.status_code == 200
    assert response.json()["providers"]["video"] == {
        "configured": True,
        "hasApiKey": False,
        "model": "video-model",
        "driver": "generic_job",
        "baseUrl": "https://video.example/v1",
    }
