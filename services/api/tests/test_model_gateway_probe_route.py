from __future__ import annotations

import json

import httpx
import pytest
from fastapi.testclient import TestClient


def test_probe_text_fixture_mode(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIDEOMAKER_FIXTURE_MODE", "true")
    response = client.post(
        "/api/settings/model-gateway/test",
        json={"provider": "text"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["provider"] == "text"
    assert "Fixture" in payload["message"]


def test_probe_text_uses_saved_credentials(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("VIDEOMAKER_FIXTURE_MODE", raising=False)
    client.put(
        "/api/settings/model-gateway",
        json={
            "providers": {
                "text": {
                    "baseUrl": "https://api.example/v1",
                    "apiKey": "secret-key",
                    "model": "gpt-test",
                }
            }
        },
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/chat/completions")
        body = json.loads(request.content.decode())
        assert body["model"] == "gpt-test"
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "OK"}}]},
        )

    transport = httpx.MockTransport(handler)
    real_client = httpx.Client

    def client_factory(**kwargs: object) -> httpx.Client:
        kwargs.pop("transport", None)
        return real_client(transport=transport, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr("model_gateway.text_probe.httpx.Client", client_factory)

    response = client.post(
        "/api/settings/model-gateway/test",
        json={"provider": "text"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["replyPreview"] == "OK"
    assert payload["latencyMs"] >= 0


def test_probe_text_inline_overrides(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("VIDEOMAKER_FIXTURE_MODE", raising=False)

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode())
        assert body["model"] == "inline-model"
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "pong"}}]},
        )

    transport = httpx.MockTransport(handler)
    real_client = httpx.Client

    def client_factory(**kwargs: object) -> httpx.Client:
        kwargs.pop("transport", None)
        return real_client(transport=transport, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr("model_gateway.text_probe.httpx.Client", client_factory)

    response = client.post(
        "/api/settings/model-gateway/test",
        json={
            "provider": "text",
            "baseUrl": "https://inline.example/v1",
            "apiKey": "inline-key",
            "model": "inline-model",
        },
    )
    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert response.json()["replyPreview"] == "pong"


def test_probe_video_understanding_fixture_mode(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VIDEOMAKER_FIXTURE_MODE", "true")
    response = client.post(
        "/api/settings/model-gateway/test",
        json={"provider": "videoUnderstanding"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["provider"] == "videoUnderstanding"


def test_probe_rejects_invalid_provider(client: TestClient) -> None:
    response = client.post(
        "/api/settings/model-gateway/test",
        json={"provider": "vision"},
    )
    assert response.status_code == 422
