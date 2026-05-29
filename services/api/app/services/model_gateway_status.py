from __future__ import annotations

import os
from typing import TypedDict


class ProviderStatus(TypedDict):
    configured: bool
    model: str | None
    driver: str


class ModelGatewayStatusResponse(TypedDict):
    fixtureMode: bool
    providers: dict[str, ProviderStatus]


# Keep env key names in sync with services/worker/app/gateway/config.py
_TEXT_DEFAULT_MODEL = "gpt-4o-mini"
_TTS_DEFAULT_MODEL = "tts-1"
_IMAGE_DEFAULT_MODEL = "dall-e-3"
_VIDEO_DEFAULT_DRIVER = "generic_job"


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _bool_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _provider_status(
    *,
    configured: bool,
    model: str,
    driver: str,
) -> ProviderStatus:
    return {
        "configured": configured,
        "model": model if configured else None,
        "driver": driver,
    }


def get_model_gateway_status() -> ModelGatewayStatusResponse:
    text_api_key = _env("TEXT_API_KEY")
    text_model = _env("TEXT_MODEL", _TEXT_DEFAULT_MODEL)

    vision_api_key = _env("VISION_API_KEY") or text_api_key
    vision_model = _env("VISION_MODEL") or text_model

    tts_api_key = _env("TTS_API_KEY")
    tts_model = _env("TTS_MODEL", _TTS_DEFAULT_MODEL)

    image_api_key = _env("IMAGE_API_KEY")
    image_model = _env("IMAGE_MODEL", _IMAGE_DEFAULT_MODEL)

    video_base_url = _env("VIDEO_API_BASE")
    video_model = _env("VIDEO_MODEL")
    video_driver = _env("VIDEO_DRIVER", _VIDEO_DEFAULT_DRIVER)

    return {
        "fixtureMode": _bool_env("VIDEOMAKER_FIXTURE_MODE"),
        "providers": {
            "text": _provider_status(
                configured=bool(text_api_key),
                model=text_model,
                driver="openai_compatible",
            ),
            "vision": _provider_status(
                configured=bool(vision_api_key),
                model=vision_model,
                driver="openai_compatible",
            ),
            "tts": _provider_status(
                configured=bool(tts_api_key),
                model=tts_model,
                driver="openai_compatible",
            ),
            "image": _provider_status(
                configured=bool(image_api_key),
                model=image_model,
                driver="openai_compatible",
            ),
            "video": _provider_status(
                configured=bool(video_base_url),
                model=video_model,
                driver=video_driver,
            ),
        },
    }
