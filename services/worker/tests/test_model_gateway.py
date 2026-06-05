from __future__ import annotations

import json
import os
from typing import Any

import httpx
import pytest

from model_gateway.store import ModelGatewayStore

from app.gateway.config import GatewayConfig
from app.gateway.model_gateway import ModelGateway
from app.gateway.providers.base import GatewayError, ProviderConfig
from app.gateway.providers.openai_compatible_chat import OpenAICompatibleChatProvider
from app.gateway.providers.pluggable_video import GenericJobVideoProvider


def test_gateway_error_retryable() -> None:
    err = GatewayError(code="rate_limit", message="429", retryable=True)
    assert err.retryable is True
    assert err.code == "rate_limit"


def test_gateway_config_vision_falls_back_to_text(tmp_path) -> None:
    store = ModelGatewayStore(tmp_path / "db.sqlite3", tmp_path / "storage")
    store.ensure_initialized()
    store.update_providers(
        {
            "text": {
                "baseUrl": "https://text.example/v1",
                "apiKey": "text-key",
                "model": "text-model",
            }
        }
    )
    config = GatewayConfig.from_store(store)
    assert config.vision.base_url == "https://text.example/v1"
    assert config.vision.api_key == "text-key"
    assert config.vision.model == "text-model"


def test_complete_json_with_mocked_httpx() -> None:
    response_payload = {
        "choices": [{"message": {"content": json.dumps({"answer": 42})}}]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/chat/completions")
        body = json.loads(request.content.decode())
        assert body["response_format"] == {"type": "json_object"}
        messages = body["messages"]
        assert "Respond with valid JSON only." in messages[0]["content"]
        return httpx.Response(200, json=response_payload)

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    config = GatewayConfig(
        text=ProviderConfig(
            base_url="https://api.example/v1",
            api_key="test-key",
            model="gpt-test",
        ),
        vision=ProviderConfig(
            base_url="https://api.example/v1",
            api_key="test-key",
            model="gpt-test",
        ),
        tts=ProviderConfig("https://api.example/v1", "test-key", "tts-1"),
        image=ProviderConfig("https://api.example/v1", "test-key", "dall-e-3"),
        video_driver="generic_job",
        video=ProviderConfig("https://video.example/v1", "video-key", "video-model"),
    )
    gateway = ModelGateway(config=config, client=client)

    result = gateway.complete_json(
        "Summarize inputs",
        {"topic": "gateway"},
        "video-structure",
    )

    assert result == {"answer": 42}
    assert gateway.last_latency_ms is not None
    assert gateway.last_latency_ms >= 0


def test_complete_json_omits_response_format_for_volcengine() -> None:
    response_payload = {
        "choices": [{"message": {"content": json.dumps({"ok": True})}}]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode())
        assert "response_format" not in body
        return httpx.Response(200, json=response_payload)

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    config = GatewayConfig(
        text=ProviderConfig(
            base_url="https://ark.cn-beijing.volces.com/api/v3",
            api_key="test-key",
            model="doubao-vision",
        ),
        vision=ProviderConfig(
            base_url="https://ark.cn-beijing.volces.com/api/v3",
            api_key="test-key",
            model="doubao-vision",
        ),
        tts=ProviderConfig("https://api.example/v1", "test-key", "tts-1"),
        image=ProviderConfig("https://api.example/v1", "test-key", "dall-e-3"),
        video_driver="generic_job",
        video=ProviderConfig("https://video.example/v1", "video-key", "video-model"),
    )
    gateway = ModelGateway(config=config, client=client)

    result = gateway.complete_json("Task", {"x": 1}, "schema", profile="vision")

    assert result == {"ok": True}


def test_complete_text_routes_vision_profile() -> None:
    seen_models: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode())
        seen_models.append(body["model"])
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "vision ok"}}]},
        )

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    config = GatewayConfig(
        text=ProviderConfig("https://text.example/v1", "text-key", "text-model"),
        vision=ProviderConfig("https://vision.example/v1", "vision-key", "vision-model"),
        tts=ProviderConfig("https://api.example/v1", "test-key", "tts-1"),
        image=ProviderConfig("https://api.example/v1", "test-key", "dall-e-3"),
        video_driver="generic_job",
        video=ProviderConfig("https://video.example/v1", "video-key", "video-model"),
    )
    gateway = ModelGateway(config=config, client=client)

    text = gateway.complete_text("Describe", {"image": "frame-1"}, profile="vision")
    assert text == "vision ok"
    assert seen_models == ["vision-model"]


def test_complete_json_routes_vision_profile_with_image_parts() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode())
        seen["model"] = body["model"]
        user_content = body["messages"][1]["content"]
        assert isinstance(user_content, list)
        assert user_content[0]["type"] == "text"
        assert any(part.get("type") == "image_url" for part in user_content)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps({"analyses": []})}}]},
        )

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    config = GatewayConfig(
        text=ProviderConfig("https://text.example/v1", "text-key", "text-model"),
        vision=ProviderConfig("https://vision.example/v1", "vision-key", "vision-model"),
        tts=ProviderConfig("https://api.example/v1", "test-key", "tts-1"),
        image=ProviderConfig("https://api.example/v1", "test-key", "dall-e-3"),
        video_driver="generic_job",
        video=ProviderConfig("https://video.example/v1", "video-key", "video-model"),
    )
    gateway = ModelGateway(config=config, client=client)

    result = gateway.complete_json(
        "Describe moments",
        {
            "inputs": {
                "moments": [
                    {
                        "id": "moment-1",
                        "keyframeBase64": "abc123",
                    }
                ]
            }
        },
        "asset-inventory",
        profile="vision",
    )

    assert result == {"analyses": []}
    assert seen["model"] == "vision-model"


def test_complete_json_raises_gateway_error_on_invalid_json() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "not-json"}}]},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    config = GatewayConfig(
        text=ProviderConfig("https://api.example/v1", "test-key", "gpt-test"),
        vision=ProviderConfig("https://api.example/v1", "test-key", "gpt-test"),
        tts=ProviderConfig("https://api.example/v1", "test-key", "tts-1"),
        image=ProviderConfig("https://api.example/v1", "test-key", "dall-e-3"),
        video_driver="generic_job",
        video=ProviderConfig("https://video.example/v1", "video-key", "video-model"),
    )
    gateway = ModelGateway(config=config, client=client)

    with pytest.raises(GatewayError) as exc_info:
        gateway.complete_json("Task", {"x": 1}, "video-structure")

    assert exc_info.value.code == "invalid_json"
    assert exc_info.value.retryable is False


def test_chat_provider_retries_on_429(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"count": 0}
    sleeps: list[float] = []

    def fake_sleep(seconds: float) -> None:
        sleeps.append(seconds)

    monkeypatch.setattr(
        "app.gateway.providers.openai_compatible_chat.time.sleep",
        fake_sleep,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] < 3:
            return httpx.Response(429, text="rate limited")
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "ok"}}]},
        )

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    provider = OpenAICompatibleChatProvider(
        ProviderConfig("https://api.example/v1", "test-key", "gpt-test"),
        client=client,
    )

    content = provider.complete([{"role": "user", "content": "hi"}])
    assert content == "ok"
    assert calls["count"] == 3
    assert sleeps == [0.5, 1.0]


def test_chat_provider_retries_on_transport_error(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"count": 0}
    sleeps: list[float] = []

    monkeypatch.setattr(
        "app.gateway.providers.openai_compatible_chat.time.sleep",
        lambda seconds: sleeps.append(seconds),
    )

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] < 3:
            raise httpx.ConnectError("connection reset")
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "ok"}}]},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OpenAICompatibleChatProvider(
        ProviderConfig("https://api.example/v1", "test-key", "gpt-test"),
        client=client,
    )

    content = provider.complete([{"role": "user", "content": "hi"}])
    assert content == "ok"
    assert calls["count"] == 3
    assert sleeps == [0.5, 1.0]


def test_video_poll_timeout_is_retryable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.gateway.providers.pluggable_video.time.sleep",
        lambda _seconds: None,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "pending"})

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)
    provider = GenericJobVideoProvider(
        ProviderConfig("https://video.example/v1", "video-key", "video-model"),
        client=client,
        poll_interval_sec=0.0,
        max_poll_sec=0,
    )

    with pytest.raises(GatewayError) as exc_info:
        provider.poll("job-1")

    assert exc_info.value.code == "poll_timeout"
    assert exc_info.value.retryable is True


@pytest.mark.integration
def test_live_text_completion_skipped_by_default() -> None:
    if os.getenv("RUN_INTEGRATION") != "1":
        pytest.skip("Set RUN_INTEGRATION=1 to run live gateway tests")
    api_key = os.getenv("TEXT_API_KEY")
    if not api_key:
        pytest.skip("TEXT_API_KEY is required for live gateway tests")

    config = GatewayConfig(
        text=ProviderConfig(
            base_url=os.getenv("TEXT_API_BASE", "https://api.openai.com/v1"),
            api_key=api_key,
            model=os.getenv("TEXT_MODEL", "gpt-4o-mini"),
        ),
        vision=ProviderConfig(
            base_url=os.getenv("VISION_API_BASE", "https://api.openai.com/v1"),
            api_key=os.getenv("VISION_API_KEY", api_key),
            model=os.getenv("VISION_MODEL", "gpt-4o-mini"),
        ),
        tts=ProviderConfig(base_url="https://api.openai.com/v1", api_key="", model="tts-1"),
        image=ProviderConfig(base_url="https://api.openai.com/v1", api_key="", model="dall-e-3"),
        video_driver="generic_job",
        video=ProviderConfig(base_url="", api_key="", model=""),
    )
    gateway = ModelGateway(config=config)
    result = gateway.complete_text("Reply with the word ok", {"check": True})
    assert isinstance(result, str)
    assert result
