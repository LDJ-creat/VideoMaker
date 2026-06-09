from __future__ import annotations

from model_gateway.constants import DEFAULT_VOLCENGINE_TTS_BASE_URL


def resolve_effective_tts_driver(driver: str) -> str:
    normalized = (driver or "").strip().lower()
    if normalized == "volcengine_tts":
        return "volcengine_tts"
    return normalized or "openai_compatible"


def resolve_tts_base_url(base_url: str, *, driver: str) -> str:
    stored = (base_url or "").strip()
    if stored:
        return stored
    if resolve_effective_tts_driver(driver) == "volcengine_tts":
        return DEFAULT_VOLCENGINE_TTS_BASE_URL
    return stored
