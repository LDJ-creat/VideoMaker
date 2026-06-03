from __future__ import annotations

import base64

import httpx

from app.gateway.providers.base import ProviderConfig
from app.gateway.providers.dashscope_tts import _extract_audio_bytes, synthesize_dashscope
from app.gateway.providers.openai_compatible_tts import OpenAICompatibleTTSProvider


def test_extract_audio_bytes_from_dashscope_payload() -> None:
    payload = {"output": {"audio": {"data": base64.b64encode(b"wav-bytes").decode("ascii")}}}
    client = httpx.Client()
    try:
        assert _extract_audio_bytes(payload, client=client) == b"wav-bytes"
    finally:
        client.close()


def test_extract_audio_bytes_downloads_dashscope_audio_url() -> None:
    payload = {"output": {"audio": {"url": "https://example.com/voice.wav"}}}

    class FakeClient:
        def get(self, url: str) -> httpx.Response:
            assert url == "https://example.com/voice.wav"
            return httpx.Response(200, content=b"downloaded-wav")

    assert _extract_audio_bytes(payload, client=FakeClient()) == b"downloaded-wav"  # type: ignore[arg-type]


def test_synthesize_dashscope_posts_speech_synthesizer(monkeypatch) -> None:
    config = ProviderConfig(
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        model="cosyvoice-v3-plus",
        api_key="test-key",
    )
    captured: dict = {}

    class FakeClient:
        def post(self, url, *, headers, json):  # type: ignore[no-untyped-def]
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            return httpx.Response(
                200,
                json={"output": {"audio": {"data": base64.b64encode(b"RIFF").decode("ascii")}}},
            )

    result = synthesize_dashscope(
        config,
        "你好",
        options={"voice": "default"},
        client=FakeClient(),  # type: ignore[arg-type]
    )
    assert result == b"RIFF"
    assert "SpeechSynthesizer" in captured["url"]
    assert captured["json"]["model"] == "cosyvoice-v3-plus"
    assert captured["json"]["input"]["voice"] == "longanyang"
    assert captured["json"]["input"]["text"] == "你好"


def test_openai_compatible_tts_routes_dashscope_host(monkeypatch) -> None:
    config = ProviderConfig(
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        model="cosyvoice-v3-plus",
        api_key="test-key",
    )

    class FakeClient:
        def post(self, url, *, headers, json):  # type: ignore[no-untyped-def]
            return httpx.Response(
                200,
                json={"output": {"audio": {"data": base64.b64encode(b"wav").decode("ascii")}}},
            )

        def close(self) -> None:
            return None

    provider = OpenAICompatibleTTSProvider(config, client=FakeClient())  # type: ignore[arg-type]
    assert provider.synthesize("测试") == b"wav"
