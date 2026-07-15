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


def test_probe_text_chat_disables_thinking_for_deepseek() -> None:
    seen_body: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_body
        seen_body = json.loads(request.content.decode())
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "OK"}}]},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = probe_text_chat(
        base_url="https://api.deepseek.com/v1",
        api_key="secret",
        model="deepseek-v4-flash",
        client=client,
    )
    assert result.ok is True
    assert seen_body.get("thinking") == {"type": "disabled"}
    assert seen_body.get("max_tokens", 0) >= 64


def test_probe_text_chat_does_not_send_thinking_for_other_models() -> None:
    seen_body: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_body
        seen_body = json.loads(request.content.decode())
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
    assert "thinking" not in seen_body


def test_probe_text_chat_accepts_reasoning_content_when_content_empty() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": "",
                            "reasoning_content": "I should reply OK.",
                        }
                    }
                ]
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = probe_text_chat(
        base_url="https://api.deepseek.com/v1",
        api_key="secret",
        model="deepseek-v4-flash",
        client=client,
    )
    assert result.ok is True
    assert result.reply_preview == "I should reply OK."


def test_probe_text_chat_empty_content_still_fails() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "", "reasoning_content": ""}}]},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = probe_text_chat(
        base_url="https://api.example/v1",
        api_key="secret",
        model="gpt-test",
        client=client,
    )
    assert result.ok is False
    assert result.message == "模型返回空内容"
