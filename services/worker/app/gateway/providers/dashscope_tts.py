from __future__ import annotations

import asyncio
import base64
import json
import uuid
from typing import Any
from urllib.parse import urlparse

import httpx

from app.gateway.providers.base import GatewayError, ProviderConfig

SAMBERT_WS_URL = "wss://dashscope.aliyuncs.com/api-ws/v1/inference"

DEFAULT_DASHSCOPE_VOICE = "longanyang"


def _is_dashscope_host(base_url: str) -> bool:
    return "dashscope" in base_url.lower()


def _dashscope_api_host(base_url: str) -> str:
    parsed = urlparse(base_url)
    host = parsed.netloc.lower()
    scheme = parsed.scheme or "https"
    if "dashscope-intl" in host:
        return f"{scheme}://dashscope-intl.aliyuncs.com"
    if "dashscope-us" in host:
        return f"{scheme}://dashscope-us.aliyuncs.com"
    return f"{scheme}://dashscope.aliyuncs.com"


def _dashscope_tts_url(base_url: str) -> str:
    return f"{_dashscope_api_host(base_url)}/api/v1/services/audio/tts/SpeechSynthesizer"


def _is_sambert_model(model: str) -> bool:
    return model.lower().startswith("sambert-")


def _map_dashscope_voice(voice: str) -> str:
    normalized = voice.strip()
    if not normalized or normalized == "default":
        return DEFAULT_DASHSCOPE_VOICE
    return normalized


def _build_tts_body(model: str, text: str, *, voice: str) -> dict[str, Any]:
    """CosyVoice expects input.voice; Sambert uses model id as the voice preset."""
    if _is_sambert_model(model):
        return {
            "model": model,
            "input": {"text": text},
            "parameters": {
                "format": "wav",
                "sample_rate": 48000,
            },
        }
    return {
        "model": model,
        "input": {
            "text": text,
            "voice": voice,
            "format": "wav",
            "sample_rate": 24000,
        },
    }


def _extract_audio_bytes(payload: dict[str, Any], *, client: httpx.Client) -> bytes:
    output = payload.get("output")
    if not isinstance(output, dict):
        raise GatewayError(
            code="invalid_response",
            message=f"Unexpected DashScope TTS response: {payload}",
            retryable=False,
        )
    audio = output.get("audio")
    if isinstance(audio, dict):
        data = audio.get("data")
        if isinstance(data, str) and data.strip():
            return base64.b64decode(data)
        url = audio.get("url")
        if isinstance(url, str) and url.strip():
            try:
                download = client.get(url.strip())
            except httpx.HTTPError as exc:
                raise GatewayError(
                    code="transport_error",
                    message=f"Failed to download DashScope TTS audio: {exc}",
                    retryable=True,
                ) from exc
            if download.status_code >= 400:
                raise GatewayError(
                    code="http_error",
                    message=f"HTTP {download.status_code} downloading TTS audio",
                    retryable=download.status_code in {429, 502, 503},
                )
            return download.content
    raise GatewayError(
        code="invalid_response",
        message=f"DashScope TTS response missing audio data: {payload}",
        retryable=False,
    )


def _sambert_run_task_message(model: str, text: str) -> dict[str, Any]:
    return {
        "header": {
            "action": "run-task",
            "task_id": uuid.uuid4().hex,
            "streaming": "out",
        },
        "payload": {
            "model": model,
            "task_group": "audio",
            "task": "tts",
            "function": "SpeechSynthesizer",
            "input": {"text": text},
            "parameters": {
                "text_type": "PlainText",
                "format": "wav",
                "sample_rate": 48000,
            },
        },
    }


async def _sambert_websocket_synthesize_async(*, api_key: str, model: str, text: str) -> bytes:
    import websockets

    headers = {"Authorization": f"Bearer {api_key}"}
    message = _sambert_run_task_message(model, text)
    audio_chunks: list[bytes] = []

    async with websockets.connect(
        SAMBERT_WS_URL,
        additional_headers=headers,
        open_timeout=30,
        close_timeout=10,
    ) as websocket:
        await websocket.send(json.dumps(message, ensure_ascii=False))
        while True:
            frame = await asyncio.wait_for(websocket.recv(), timeout=120)
            if isinstance(frame, bytes):
                audio_chunks.append(frame)
                continue
            payload = json.loads(frame)
            header = payload.get("header") if isinstance(payload, dict) else None
            if not isinstance(header, dict):
                continue
            event = str(header.get("event", ""))
            if event == "task-finished":
                break
            if event == "task-failed":
                raise GatewayError(
                    code="tts_failed",
                    message=str(
                        header.get("error_message")
                        or payload.get("payload")
                        or "Sambert task failed"
                    ),
                    retryable=False,
                )

    if not audio_chunks:
        raise GatewayError(
            code="invalid_response",
            message="Sambert WebSocket returned no audio data",
            retryable=False,
        )
    return b"".join(audio_chunks)


def synthesize_sambert_websocket(config: ProviderConfig, text: str, *, model: str) -> bytes:
    if not config.api_key:
        raise GatewayError(
            code="missing_api_key",
            message="TTS provider API key is not configured",
            retryable=False,
        )
    return asyncio.run(
        _sambert_websocket_synthesize_async(
            api_key=config.api_key,
            model=model,
            text=text,
        )
    )


def synthesize_dashscope(
    config: ProviderConfig,
    text: str,
    *,
    options: dict[str, Any] | None,
    client: httpx.Client,
) -> bytes:
    if not config.api_key:
        raise GatewayError(
            code="missing_api_key",
            message="TTS provider API key is not configured",
            retryable=False,
        )

    opts = options or {}
    voice = _map_dashscope_voice(str(opts.get("voice", "default")))
    model = str(opts.get("model", config.model))
    if _is_sambert_model(model):
        return synthesize_sambert_websocket(config, text, model=model)

    url = _dashscope_tts_url(config.base_url)
    body = _build_tts_body(model, text, voice=voice)
    headers = {
        "Authorization": f"Bearer {config.api_key}",
        "Content-Type": "application/json",
    }

    try:
        response = client.post(url, headers=headers, json=body)
    except httpx.HTTPError as exc:
        raise GatewayError(
            code="transport_error",
            message=str(exc),
            retryable=True,
        ) from exc

    if response.status_code >= 400:
        raise GatewayError(
            code="http_error",
            message=f"HTTP {response.status_code}: {response.text}",
            retryable=response.status_code in {429, 502, 503},
        )

    content_type = response.headers.get("content-type", "").lower()
    if "audio" in content_type or "octet-stream" in content_type:
        return response.content

    try:
        payload = response.json()
    except ValueError as exc:
        raise GatewayError(
            code="invalid_response",
            message=f"DashScope TTS returned non-JSON body: {response.text[:200]}",
            retryable=False,
        ) from exc

    return _extract_audio_bytes(payload, client=client)
