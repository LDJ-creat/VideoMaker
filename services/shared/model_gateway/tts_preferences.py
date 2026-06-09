from __future__ import annotations

from typing import Any, TypedDict


class TtsPreferences(TypedDict):
    resourceId: str
    speaker: str
    modelVariant: str
    speechRate: int
    loudnessRate: int
    emotion: str | None
    emotionScale: int
    contextTexts: str
    explicitLanguage: str
    format: str
    sampleRate: int
    chunkCharLimit: int


DEFAULT_TTS_PREFERENCES: TtsPreferences = {
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

_INT_FIELDS = frozenset(
    {"speechRate", "loudnessRate", "emotionScale", "sampleRate", "chunkCharLimit"}
)
_STR_FIELDS = frozenset(
    {
        "resourceId",
        "speaker",
        "modelVariant",
        "contextTexts",
        "explicitLanguage",
        "format",
    }
)


def normalize_tts_preferences(raw: dict[str, Any] | None) -> TtsPreferences:
    merged: dict[str, Any] = dict(DEFAULT_TTS_PREFERENCES)
    if isinstance(raw, dict):
        for key in DEFAULT_TTS_PREFERENCES:
            if key not in raw:
                continue
            value = raw[key]
            if key == "emotion":
                merged[key] = str(value).strip() if value not in (None, "") else None
                continue
            if key in _INT_FIELDS:
                try:
                    merged[key] = int(value)
                except (TypeError, ValueError):
                    continue
            elif key in _STR_FIELDS:
                merged[key] = str(value).strip()
    return _validate_tts_preferences(merged)


def patch_tts_preferences(
    current: TtsPreferences,
    patch: dict[str, Any],
) -> TtsPreferences:
    merged: dict[str, Any] = dict(current)
    for key, value in patch.items():
        if key not in DEFAULT_TTS_PREFERENCES:
            raise ValueError(f"Unknown tts preference: {key}")
        if key == "emotion":
            if value is None:
                merged[key] = None
            else:
                stripped = str(value).strip()
                merged[key] = stripped or None
            continue
        if key in _INT_FIELDS:
            merged[key] = int(value)
        elif key in _STR_FIELDS:
            stripped = str(value).strip()
            if not stripped and key in {"resourceId", "speaker", "explicitLanguage", "format"}:
                raise ValueError(f"{key} must be non-empty")
            merged[key] = stripped
    return _validate_tts_preferences(merged)


def _validate_tts_preferences(raw: dict[str, Any]) -> TtsPreferences:
    speech_rate = int(raw["speechRate"])
    loudness_rate = int(raw["loudnessRate"])
    emotion_scale = int(raw["emotionScale"])
    sample_rate = int(raw["sampleRate"])
    chunk_limit = int(raw["chunkCharLimit"])

    if not -50 <= speech_rate <= 100:
        raise ValueError("speechRate must be between -50 and 100")
    if not -50 <= loudness_rate <= 100:
        raise ValueError("loudnessRate must be between -50 and 100")
    if not 1 <= emotion_scale <= 5:
        raise ValueError("emotionScale must be between 1 and 5")
    if sample_rate <= 0:
        raise ValueError("sampleRate must be positive")
    if chunk_limit < 64:
        raise ValueError("chunkCharLimit must be at least 64")

    model_variant = str(raw["modelVariant"]).strip()
    if model_variant not in {"seed-tts-2.0-standard", "seed-tts-2.0-expressive", ""}:
        raise ValueError("modelVariant must be seed-tts-2.0-standard or seed-tts-2.0-expressive")

    audio_format = str(raw["format"]).strip().lower()
    if audio_format not in {"pcm", "mp3", "ogg_opus"}:
        raise ValueError("format must be pcm, mp3, or ogg_opus")

    return TtsPreferences(
        resourceId=str(raw["resourceId"]).strip(),
        speaker=str(raw["speaker"]).strip(),
        modelVariant=model_variant or DEFAULT_TTS_PREFERENCES["modelVariant"],
        speechRate=speech_rate,
        loudnessRate=loudness_rate,
        emotion=raw.get("emotion") if raw.get("emotion") in (None, "") else str(raw["emotion"]).strip(),
        emotionScale=emotion_scale,
        contextTexts=str(raw["contextTexts"]),
        explicitLanguage=str(raw["explicitLanguage"]).strip(),
        format=audio_format,
        sampleRate=sample_rate,
        chunkCharLimit=chunk_limit,
    )
