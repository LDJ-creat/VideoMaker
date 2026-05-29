from __future__ import annotations

import os
from dataclasses import dataclass

from app.gateway.providers.base import ProviderConfig


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _bool_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class GatewayConfig:
    text: ProviderConfig
    vision: ProviderConfig
    tts: ProviderConfig
    image: ProviderConfig
    video_driver: str
    video: ProviderConfig
    fixture_mode: bool = False
    max_poll_sec: int = 300
    poll_interval_sec: float = 3.0

    @classmethod
    def from_env(cls) -> GatewayConfig:
        text = ProviderConfig(
            base_url=_env("TEXT_API_BASE", "https://api.openai.com/v1"),
            api_key=_env("TEXT_API_KEY"),
            model=_env("TEXT_MODEL", "gpt-4o-mini"),
        )
        vision_base = _env("VISION_API_BASE") or text.base_url
        vision_key = _env("VISION_API_KEY") or text.api_key
        vision_model = _env("VISION_MODEL") or text.model
        vision = ProviderConfig(
            base_url=vision_base,
            api_key=vision_key,
            model=vision_model,
        )
        tts = ProviderConfig(
            base_url=_env("TTS_API_BASE", "https://api.openai.com/v1"),
            api_key=_env("TTS_API_KEY"),
            model=_env("TTS_MODEL", "tts-1"),
        )
        image = ProviderConfig(
            base_url=_env("IMAGE_API_BASE", "https://api.openai.com/v1"),
            api_key=_env("IMAGE_API_KEY"),
            model=_env("IMAGE_MODEL", "dall-e-3"),
        )
        video = ProviderConfig(
            base_url=_env("VIDEO_API_BASE"),
            api_key=_env("VIDEO_API_KEY"),
            model=_env("VIDEO_MODEL", ""),
        )
        return cls(
            text=text,
            vision=vision,
            tts=tts,
            image=image,
            video_driver=_env("VIDEO_DRIVER", "generic_job"),
            video=video,
            fixture_mode=_bool_env("VIDEOMAKER_FIXTURE_MODE"),
        )
