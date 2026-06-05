from __future__ import annotations

import json

import httpx

from model_gateway.text_probe import probe_text_chat


def test_probe_text_chat_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode())
        assert body["model"] == "gpt-test"
        assert body["messages"][0]["content"] == "Reply with exactly: OK"
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "OK"}}]},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = probe_text_chat(
        base_url="https://api.example/v1",
        api_key="secret",
        model="gpt-test",
        client=client,
    )
    assert result.ok is True
    assert result.reply_preview == "OK"
    assert result.latency_ms >= 0


def test_probe_text_chat_missing_api_key() -> None:
    result = probe_text_chat(
        base_url="https://api.example/v1",
        api_key="",
        model="gpt-test",
    )
    assert result.ok is False
    assert result.detail == "missing_api_key"


def test_probe_text_chat_http_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text='{"error":"invalid key"}')

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = probe_text_chat(
        base_url="https://api.example/v1",
        api_key="bad",
        model="gpt-test",
        client=client,
    )
    assert result.ok is False
    assert "401" in result.message


def test_probe_text_chat_accepts_full_chat_completions_url() -> None:
    seen_path = ""

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_path
        seen_path = request.url.path
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "OK"}}]},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = probe_text_chat(
        base_url="https://ark.cn-beijing.volces.com/api/v3/chat/completions",
        api_key="secret",
        model="doubao-test",
        client=client,
    )
    assert result.ok is True
    assert seen_path == "/api/v3/chat/completions"
