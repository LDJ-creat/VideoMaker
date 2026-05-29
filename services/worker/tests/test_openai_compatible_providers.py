from __future__ import annotations

import base64
import json

import httpx

from app.gateway.model_gateway import ModelGateway
from app.gateway.providers.base import ProviderConfig
from app.gateway.config import GatewayConfig
from app.gateway.providers.openai_compatible_chat import OpenAICompatibleChatProvider
from app.gateway.providers.openai_compatible_image import OpenAICompatibleImageProvider
from app.gateway.providers.openai_compatible_tts import OpenAICompatibleTTSProvider
from app.gateway.providers.pluggable_video import GenericJobVideoProvider


def _gateway_config() -> GatewayConfig:
    return GatewayConfig(
        text=ProviderConfig("https://api.example/v1", "test-key", "gpt-test"),
        vision=ProviderConfig("https://api.example/v1", "test-key", "gpt-test"),
        tts=ProviderConfig("https://api.example/v1", "test-key", "tts-1"),
        image=ProviderConfig("https://api.example/v1", "test-key", "dall-e-3"),
        video_driver="generic_job",
        video=ProviderConfig("https://video.example/v1", "video-key", "video-model"),
    )


def test_openai_chat_provider_parses_assistant_message() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "assistant says hi"}}]},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OpenAICompatibleChatProvider(
        ProviderConfig("https://api.example/v1", "test-key", "gpt-test"),
        client=client,
    )

    content = provider.complete([{"role": "user", "content": "hello"}])
    assert content == "assistant says hi"


def test_openai_tts_provider_returns_audio_bytes() -> None:
    wav = b"RIFF----WAVEfmt "

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode())
        assert request.url.path.endswith("/audio/speech")
        assert body == {"model": "tts-1", "input": "hello", "voice": "alloy"}
        return httpx.Response(200, content=wav)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OpenAICompatibleTTSProvider(
        ProviderConfig("https://api.example/v1", "test-key", "tts-1"),
        client=client,
    )

    audio = provider.synthesize("hello")
    assert audio == wav


def test_openai_image_provider_decodes_b64_json() -> None:
    png = b"\x89PNG\r\n\x1a\nfake-image"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/images/generations")
        return httpx.Response(
            200,
            json={"data": [{"b64_json": base64.b64encode(png).decode()}]},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OpenAICompatibleImageProvider(
        ProviderConfig("https://api.example/v1", "test-key", "dall-e-3"),
        client=client,
    )

    image = provider.generate("a red square")
    assert image == png


def test_openai_image_provider_downloads_url() -> None:
    png = b"\x89PNG\r\n\x1a\nurl-image"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/images/generations"):
            return httpx.Response(
                200,
                json={"data": [{"url": "https://cdn.example/image.png"}]},
            )
        if str(request.url) == "https://cdn.example/image.png":
            return httpx.Response(200, content=png)
        raise AssertionError(f"unexpected url: {request.url}")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = OpenAICompatibleImageProvider(
        ProviderConfig("https://api.example/v1", "test-key", "dall-e-3"),
        client=client,
    )

    image = provider.generate("a blue circle")
    assert image == png


def test_gateway_generate_image_and_tts() -> None:
    png = b"\x89PNG\r\n\x1a\n"
    wav = b"RIFF----WAVEfmt "

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/images/generations"):
            return httpx.Response(
                200,
                json={"data": [{"b64_json": base64.b64encode(png).decode()}]},
            )
        if request.url.path.endswith("/audio/speech"):
            return httpx.Response(200, content=wav)
        raise AssertionError(f"unexpected url: {request.url}")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    gateway = ModelGateway(config=_gateway_config(), client=client)

    image = gateway.generate_image("prompt")
    speech = gateway.synthesize_speech("hello")

    assert image == png
    assert speech == wav


def test_generic_video_submit_and_poll() -> None:
    video_bytes = b"fake-mp4-bytes"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path.endswith("/videos"):
            body = json.loads(request.content.decode())
            assert body["prompt"] == "make a clip"
            return httpx.Response(200, json={"jobId": "job-123"})
        if request.method == "GET" and request.url.path.endswith("/videos/job-123"):
            return httpx.Response(
                200,
                json={
                    "status": "succeeded",
                    "downloadUrl": "https://cdn.example/video.mp4",
                },
            )
        if str(request.url) == "https://cdn.example/video.mp4":
            return httpx.Response(200, content=video_bytes)
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = GenericJobVideoProvider(
        ProviderConfig("https://video.example/v1", "video-key", "video-model"),
        client=client,
        poll_interval_sec=0.0,
        max_poll_sec=30,
    )

    job_id = provider.submit("make a clip", {})
    result = provider.poll(job_id)

    assert job_id == "job-123"
    assert result.status == "succeeded"
    assert result.video_bytes == video_bytes


def test_gateway_video_job_lifecycle() -> None:
    video_bytes = b"gateway-video"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST" and request.url.path.endswith("/videos"):
            return httpx.Response(200, json={"jobId": "job-abc"})
        if request.method == "GET" and request.url.path.endswith("/videos/job-abc"):
            return httpx.Response(
                200,
                json={
                    "status": "succeeded",
                    "downloadUrl": "https://cdn.example/out.mp4",
                },
            )
        if str(request.url) == "https://cdn.example/out.mp4":
            return httpx.Response(200, content=video_bytes)
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    gateway = ModelGateway(config=_gateway_config(), client=client)

    job_id = gateway.submit_video_job("create ad")
    result = gateway.poll_video_job(job_id)

    assert job_id == "job-abc"
    assert result.video_bytes == video_bytes
