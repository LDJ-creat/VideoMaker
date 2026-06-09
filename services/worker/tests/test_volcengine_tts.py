from __future__ import annotations

import base64
import json

import pytest

from app.gateway.providers.base import ProviderConfig, GatewayError
from app.gateway.providers.volcengine_tts import (
    VolcengineTTSConfig,
    _build_request_body,
    chunk_text_for_tts,
    pcm_to_wav,
    synthesize_volcengine,
)


def test_chunk_text_for_tts_splits_long_master() -> None:
    text = "第一句。" * 50
    chunks = chunk_text_for_tts(text, limit=40)
    assert len(chunks) > 1
    assert "".join(chunks) == text


def test_pcm_to_wav_writes_riff_header() -> None:
    wav = pcm_to_wav(b"\x00\x01" * 100, sample_rate=24000)
    assert wav.startswith(b"RIFF")
    assert b"WAVE" in wav


def test_build_request_body_includes_additions_as_json_string() -> None:
    config = VolcengineTTSConfig.from_sources(
        {
            "resourceId": "seed-tts-2.0",
            "speaker": "zh_female_vv_uranus_bigtts",
            "modelVariant": "seed-tts-2.0-expressive",
            "speechRate": 10,
            "loudnessRate": 0,
            "emotion": "happy",
            "emotionScale": 4,
            "contextTexts": "自然口播",
            "explicitLanguage": "zh",
            "format": "pcm",
            "sampleRate": 24000,
            "chunkCharLimit": 400,
        },
        generation_id="gen-1",
    )
    body = _build_request_body("你好", config)
    assert body["req_params"]["speaker"] == "zh_female_vv_uranus_bigtts"
    assert body["req_params"]["audio_params"]["speech_rate"] == 10
    additions = json.loads(body["req_params"]["additions"])
    assert additions["context_texts"] == ["自然口播"]
    assert additions["section_id"] == "gen-1"


def test_synthesize_volcengine_collects_stream_chunks() -> None:
    pcm = b"\x00\x00" * 120
    payload_audio = json.dumps(
        {"code": 0, "message": "", "data": base64.b64encode(pcm).decode("ascii")}
    )
    payload_done = json.dumps({"code": 20000000, "message": "ok", "data": None})

    class FakeStreamResponse:
        status_code = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def iter_lines(self):
            yield payload_audio.encode("utf-8")
            yield payload_done.encode("utf-8")

        def read(self):
            return b""

    class FakeClient:
        def stream(self, method, url, *, headers, json):  # type: ignore[no-untyped-def]
            assert method == "POST"
            assert "unidirectional" in url
            assert headers["X-Api-Resource-Id"] == "seed-tts-2.0"
            return FakeStreamResponse()

    config = ProviderConfig(
        "https://openspeech.bytedance.com/api/v3/tts/unidirectional",
        "test-key",
        "",
    )
    wav = synthesize_volcengine(
        config,
        "测试文本",
        preferences={"resourceId": "seed-tts-2.0", "speaker": "zh_female_vv_uranus_bigtts"},
        options={"generationId": "gen-1"},
        client=FakeClient(),  # type: ignore[arg-type]
    )
    assert wav.startswith(b"RIFF")


def test_synthesize_volcengine_raises_on_empty_stream() -> None:
    class FakeStreamResponse:
        status_code = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def iter_lines(self):
            yield json.dumps({"code": 20000000, "message": "ok", "data": None}).encode(
                "utf-8"
            )

        def read(self):
            return b""

    class FakeClient:
        def stream(self, method, url, *, headers, json):  # type: ignore[no-untyped-def]
            return FakeStreamResponse()

    config = ProviderConfig(
        "https://openspeech.bytedance.com/api/v3/tts/unidirectional",
        "test-key",
        "",
    )
    with pytest.raises(GatewayError, match="no audio data"):
        synthesize_volcengine(
            config,
            "空",
            preferences={"speaker": "zh_female_vv_uranus_bigtts"},
            options=None,
            client=FakeClient(),  # type: ignore[arg-type]
        )
