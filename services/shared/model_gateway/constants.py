from __future__ import annotations

PROVIDERS = ("text", "vision", "tts", "image", "video")

DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODELS: dict[str, str] = {
    "text": "gpt-4o-mini",
    "vision": "gpt-4o-mini",
    "tts": "tts-1",
    "image": "dall-e-3",
    "video": "wan2.6-t2v",
}
DEFAULT_DRIVERS: dict[str, str] = {
    "text": "openai_compatible",
    "vision": "openai_compatible",
    "tts": "openai_compatible",
    "image": "openai_compatible",
    "video": "generic_job",
}
