from __future__ import annotations

import base64
import io
import json
import time
import uuid
import wave
from dataclasses import dataclass
from typing import Any

import httpx

from app.gateway.providers.base import GatewayError, ProviderConfig
from app.pipelines.master_narration import split_master_into_clauses

try:
    from model_gateway.fixture import is_fixture_mode
except ImportError:  # pragma: no cover

    def is_fixture_mode() -> bool:
        return False

try:
    from model_gateway.tts_preferences import DEFAULT_TTS_PREFERENCES
except ImportError:  # pragma: no cover
    DEFAULT_TTS_PREFERENCES = {
        "resourceId": "seed-tts-2.0",
        "speaker": "zh_female_vv_uranus_bigtts",
        "modelVariant": "seed-tts-2.0-expressive",
        "speechRate": 0,
        "loudnessRate": 0,
        "emotion": None,
        "emotionScale": 4,
        "contextTexts": "",
        "explicitLanguage": "zh",
        "format": "pcm",
        "sampleRate": 24000,
        "chunkCharLimit": 400,
    }

_SUCCESS_END_CODE = 20000000
_TEXT_LIMIT_CODE = 40402003


@dataclass(frozen=True)
class VolcengineTTSConfig:
    resource_id: str
    speaker: str
    model_variant: str
    speech_rate: int
    loudness_rate: int
    emotion: str | None
    emotion_scale: int
    context_texts: str
    explicit_language: str
    audio_format: str
    sample_rate: int
    chunk_char_limit: int
    section_id: str | None = None

    @classmethod
    def from_sources(
        cls,
        preferences: dict[str, Any],
        *,
        call_options: dict[str, Any] | None = None,
        generation_id: str | None = None,
    ) -> VolcengineTTSConfig:
        prefs = dict(preferences or DEFAULT_TTS_PREFERENCES)
        opts = call_options or {}
        section_id = str(opts.get("sectionId") or generation_id or "").strip() or None
        return cls(
            resource_id=str(opts.get("resourceId") or prefs.get("resourceId") or "seed-tts-2.0"),
            speaker=str(opts.get("speaker") or prefs.get("speaker") or "zh_female_vv_uranus_bigtts"),
            model_variant=str(
                opts.get("modelVariant")
                or prefs.get("modelVariant")
                or "seed-tts-2.0-expressive"
            ),
            speech_rate=int(opts.get("speechRate", prefs.get("speechRate", 0))),
            loudness_rate=int(opts.get("loudnessRate", prefs.get("loudnessRate", 0))),
            emotion=_optional_str(opts.get("emotion", prefs.get("emotion"))),
            emotion_scale=int(opts.get("emotionScale", prefs.get("emotionScale", 4))),
            context_texts=str(opts.get("contextTexts", prefs.get("contextTexts", ""))),
            explicit_language=str(
                opts.get("explicitLanguage", prefs.get("explicitLanguage", "zh"))
            ),
            audio_format=str(opts.get("format", prefs.get("format", "pcm"))).lower(),
            sample_rate=int(opts.get("sampleRate", prefs.get("sampleRate", 24000))),
            chunk_char_limit=int(opts.get("chunkCharLimit", prefs.get("chunkCharLimit", 400))),
            section_id=section_id,
        )


def _optional_str(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value).strip() or None


def chunk_text_for_tts(text: str, *, limit: int) -> list[str]:
    cleaned = str(text).strip()
    if not cleaned:
        return []
    if len(cleaned) <= limit:
        return [cleaned]

    clauses = split_master_into_clauses(cleaned)
    if not clauses:
        return [cleaned]

    chunks: list[str] = []
    current = ""
    for clause in clauses:
        candidate = f"{current}{clause}" if current else clause
        if len(candidate) <= limit:
            current = candidate
            continue
        if current:
            chunks.append(current)
        if len(clause) <= limit:
            current = clause
        else:
            for index in range(0, len(clause), limit):
                chunks.append(clause[index : index + limit])
            current = ""
    if current:
        chunks.append(current)
    return chunks or [cleaned]


def pcm_to_wav(pcm: bytes, *, sample_rate: int, channels: int = 1, sample_width: int = 2) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(channels)
        handle.setsampwidth(sample_width)
        handle.setframerate(sample_rate)
        handle.writeframes(pcm)
    return buffer.getvalue()


def _fixture_wav_bytes() -> bytes:
    pcm = b"\x00\x00" * 2400
    return pcm_to_wav(pcm, sample_rate=24000)


def _build_additions(config: VolcengineTTSConfig) -> str:
    payload: dict[str, Any] = {}
    if config.explicit_language:
        payload["explicit_language"] = config.explicit_language
    if config.section_id:
        payload["section_id"] = config.section_id
    context = str(config.context_texts).strip()
    if context:
        payload["context_texts"] = [context]
    return json.dumps(payload, ensure_ascii=False)


def _build_request_body(text: str, config: VolcengineTTSConfig) -> dict[str, Any]:
    audio_params: dict[str, Any] = {
        "format": config.audio_format,
        "sample_rate": config.sample_rate,
        "speech_rate": config.speech_rate,
        "loudness_rate": config.loudness_rate,
    }
    if config.emotion:
        audio_params["emotion"] = config.emotion
        audio_params["emotion_scale"] = config.emotion_scale

    req_params: dict[str, Any] = {
        "text": text,
        "speaker": config.speaker,
        "audio_params": audio_params,
        "additions": _build_additions(config),
    }
    if config.model_variant:
        req_params["model"] = config.model_variant
    return {
        "user": {"uid": config.section_id or "videomaker"},
        "req_params": req_params,
    }


def _parse_stream_payload(payload: dict[str, Any]) -> tuple[str, bytes | None]:
    code = payload.get("code")
    if code == _SUCCESS_END_CODE:
        return "finished", None
    if code == _TEXT_LIMIT_CODE:
        raise GatewayError(
            code="tts_text_limit",
            message=str(payload.get("message") or "TTS text length exceeded"),
            retryable=True,
        )
    if code not in (0, "0", None):
        message = str(payload.get("message") or payload)
        retryable = "quota" in message.lower() or "concurrency" in message.lower()
        raise GatewayError(code="tts_failed", message=message, retryable=retryable)

    data = payload.get("data")
    if isinstance(data, str) and data.strip():
        return "audio", base64.b64decode(data)
    return "meta", None


def _collect_audio_from_stream(response: httpx.Response) -> bytes:
    chunks: list[bytes] = []
    for raw_line in response.iter_lines():
        if not raw_line:
            continue
        line = raw_line.decode("utf-8").strip() if isinstance(raw_line, bytes) else raw_line.strip()
        if not line:
            continue
        if line.startswith("data:"):
            line = line[5:].strip()
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        kind, data = _parse_stream_payload(payload)
        if kind == "finished":
            break
        if kind == "audio" and data:
            chunks.append(data)
    if not chunks:
        raise GatewayError(
            code="invalid_response",
            message="Volcengine TTS stream returned no audio data",
            retryable=False,
        )
    return b"".join(chunks)


def _resolve_endpoint(base_url: str) -> str:
    trimmed = base_url.rstrip("/")
    if trimmed.endswith("/unidirectional"):
        return trimmed
    if "/api/v3/tts" in trimmed:
        return f"{trimmed.rstrip('/')}/unidirectional"
    return trimmed


def synthesize_volcengine_chunk(
    config: ProviderConfig,
    text: str,
    *,
    volc_config: VolcengineTTSConfig,
    client: httpx.Client,
) -> bytes:
    if not config.api_key:
        raise GatewayError(
            code="missing_api_key",
            message="TTS provider API key is not configured",
            retryable=False,
        )

    url = _resolve_endpoint(config.base_url)
    headers = {
        "X-Api-Key": config.api_key,
        "X-Api-Resource-Id": volc_config.resource_id,
        "X-Api-Request-Id": uuid.uuid4().hex,
        "Content-Type": "application/json",
    }
    body = _build_request_body(text, volc_config)

    try:
        with client.stream("POST", url, headers=headers, json=body) as response:
            if response.status_code >= 400:
                detail = response.read().decode("utf-8", errors="replace")
                raise GatewayError(
                    code="http_error",
                    message=f"HTTP {response.status_code}: {detail[:500]}",
                    retryable=response.status_code in {429, 502, 503},
                )
            return _collect_audio_from_stream(response)
    except httpx.HTTPError as exc:
        raise GatewayError(
            code="transport_error",
            message=str(exc),
            retryable=True,
        ) from exc


def synthesize_volcengine(
    config: ProviderConfig,
    text: str,
    *,
    preferences: dict[str, Any],
    options: dict[str, Any] | None,
    client: httpx.Client,
) -> bytes:
    if is_fixture_mode():
        return _fixture_wav_bytes()

    volc_config = VolcengineTTSConfig.from_sources(
        preferences,
        call_options=options,
        generation_id=str((options or {}).get("generationId") or "") or None,
    )
    chunks = chunk_text_for_tts(text, limit=volc_config.chunk_char_limit)
    if not chunks:
        raise GatewayError(
            code="invalid_input",
            message="TTS text is empty",
            retryable=False,
        )

    pcm_parts: list[bytes] = []
    for chunk in chunks:
        try:
            pcm_parts.append(
                synthesize_volcengine_chunk(
                    config,
                    chunk,
                    volc_config=volc_config,
                    client=client,
                )
            )
        except GatewayError as exc:
            if exc.code != "tts_text_limit" or volc_config.chunk_char_limit <= 64:
                raise
            smaller = max(64, volc_config.chunk_char_limit // 2)
            return synthesize_volcengine(
                config,
                text,
                preferences=preferences,
                options={**(options or {}), "chunkCharLimit": smaller},
                client=client,
            )

    pcm = b"".join(pcm_parts)
    if volc_config.audio_format == "pcm":
        return pcm_to_wav(pcm, sample_rate=volc_config.sample_rate)
    return pcm


class VolcengineTTSProvider:
    def __init__(
        self,
        config: ProviderConfig,
        *,
        preferences: dict[str, Any],
        client: httpx.Client | None = None,
        timeout_sec: float = 120.0,
    ) -> None:
        self.config = config
        self.preferences = dict(preferences or DEFAULT_TTS_PREFERENCES)
        self._client = client
        self._timeout_sec = timeout_sec
        self.last_latency_ms: int | None = None

    def _get_client(self) -> httpx.Client:
        if self._client is not None:
            return self._client
        return httpx.Client(timeout=self._timeout_sec)

    def synthesize(self, text: str, *, options: dict[str, Any] | None = None) -> bytes:
        owns_client = self._client is None
        client = self._get_client()
        started = time.perf_counter()
        try:
            result = synthesize_volcengine(
                self.config,
                text,
                preferences=self.preferences,
                options=options,
                client=client,
            )
            self.last_latency_ms = int((time.perf_counter() - started) * 1000)
            return result
        finally:
            if owns_client:
                client.close()
