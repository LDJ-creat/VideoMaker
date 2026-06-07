from __future__ import annotations

import pytest


def test_stock_media_status_unconfigured(client) -> None:
    response = client.get("/api/settings/stock-media")
    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "pexels"
    assert payload["configured"] is False
    assert payload["hasApiKey"] is False


def test_stock_media_put_and_status(client) -> None:
    response = client.put("/api/settings/stock-media", json={"apiKey": "pexels-test-key"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["configured"] is True
    assert payload["hasApiKey"] is True

    status = client.get("/api/settings/stock-media").json()
    assert status["configured"] is True


def test_stock_media_test_endpoint(client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "stock_media.store.probe_pexels_api",
        lambda *, api_key: {"ok": True, "provider": "pexels", "sampleResultCount": 100},
    )
    response = client.post("/api/settings/stock-media/test", json={"apiKey": "secret"})
    assert response.status_code == 200
    assert response.json()["ok"] is True
