from __future__ import annotations

PROVIDERS = ("text", "vision", "videoUnderstanding", "tts", "image", "video")

DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_ARK_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
DEFAULT_VOLCENGINE_TTS_BASE_URL = (
    "https://openspeech.bytedance.com/api/v3/tts/unidirectional"
)
DEFAULT_MODELS: dict[str, str] = {
    "text": "gpt-4o-mini",
    "vision": "gpt-4o-mini",
    "videoUnderstanding": "doubao-seed-1-6-250615",
    "tts": "tts-1",
    "image": "dall-e-3",
    "video": "wan2.7-t2v",
}
DEFAULT_DRIVERS: dict[str, str] = {
    "text": "openai_compatible",
    "vision": "openai_compatible",
    "videoUnderstanding": "openai_compatible",
    "tts": "openai_compatible",
    "image": "openai_compatible",
    "video": "generic_job",
}
DEFAULT_BASE_URLS: dict[str, str] = {
    "videoUnderstanding": DEFAULT_ARK_BASE_URL,
}
