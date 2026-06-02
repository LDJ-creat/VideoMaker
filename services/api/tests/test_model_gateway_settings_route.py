from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def test_put_rejects_fixture_mode(client: TestClient) -> None:
    response = client.put(
        "/api/settings/model-gateway",
        json={
            "fixtureMode": False,
            "providers": {"text": {"model": "gpt-4o-mini"}},
        },
    )
    assert response.status_code == 422


def test_put_preserves_api_key_when_omitted(client: TestClient) -> None:
    first = client.put(
        "/api/settings/model-gateway",
        json={
            "providers": {
                "text": {
                    "apiKey": "keep-me",
                    "model": "gpt-4o-mini",
                }
            }
        },
    )
    assert first.status_code == 200

    second = client.put(
        "/api/settings/model-gateway",
        json={"providers": {"text": {"model": "gpt-4o"}}},
    )
    assert second.status_code == 200
    assert second.json()["providers"]["text"]["configured"] is True
    assert second.json()["providers"]["text"]["model"] == "gpt-4o"


def test_put_clears_api_key_with_empty_string(client: TestClient) -> None:
    client.put(
        "/api/settings/model-gateway",
        json={"providers": {"text": {"apiKey": "temp", "model": "m"}}},
    )
    response = client.put(
        "/api/settings/model-gateway",
        json={"providers": {"text": {"apiKey": ""}}},
    )
    assert response.status_code == 200
    assert response.json()["providers"]["text"]["configured"] is False


def test_put_rejects_unknown_provider(client: TestClient) -> None:
    response = client.put(
        "/api/settings/model-gateway",
        json={"providers": {"unknown": {"model": "x"}}},
    )
    assert response.status_code == 422


def test_put_rejects_invalid_base_url(client: TestClient) -> None:
    response = client.put(
        "/api/settings/model-gateway",
        json={"providers": {"text": {"baseUrl": "not-a-url", "model": "m"}}},
    )
    assert response.status_code == 422


def test_put_rejects_empty_model_string(client: TestClient) -> None:
    response = client.put(
        "/api/settings/model-gateway",
        json={"providers": {"text": {"model": ""}}},
    )
    assert response.status_code == 422


def test_put_empty_body_returns_400(client: TestClient) -> None:
    response = client.put(
        "/api/settings/model-gateway",
        json={"providers": {"text": {}}},
    )
    assert response.status_code == 400
