from __future__ import annotations

import os
from dataclasses import dataclass, field

from app.gateway.providers.base import ProviderConfig

try:
    from model_gateway.store import ModelGatewayStore, ProviderCredentials
except ImportError:  # pragma: no cover - tests may construct GatewayConfig directly
    ModelGatewayStore = None  # type: ignore[misc, assignment]
    ProviderCredentials = None  # type: ignore[misc, assignment]


def resolve_max_poll_sec() -> int:
    raw = os.getenv("VIDEO_MAX_POLL_SEC", "600").strip()
    try:
        return max(60, int(raw))
    except ValueError:
        return 600


@dataclass(frozen=True)
class GatewayConfig:
    text: ProviderConfig
    vision: ProviderConfig
    video_understanding: ProviderConfig
    tts: ProviderConfig
    image: ProviderConfig
    video_driver: str
    video: ProviderConfig
    max_poll_sec: int = field(default_factory=resolve_max_poll_sec)
    poll_interval_sec: float = 3.0

    @classmethod
    def from_store(cls, store: ModelGatewayStore) -> GatewayConfig:
        credentials = store.get_credentials()
        return cls(
            text=_to_provider_config(credentials["text"]),
            vision=_to_provider_config(credentials["vision"]),
            video_understanding=_to_provider_config(credentials["videoUnderstanding"]),
            tts=_to_provider_config(credentials["tts"]),
            image=_to_provider_config(credentials["image"]),
            video_driver=credentials["video"].driver,
            video=_to_provider_config(credentials["video"]),
            max_poll_sec=resolve_max_poll_sec(),
        )


def _to_provider_config(cred: ProviderCredentials) -> ProviderConfig:
    return ProviderConfig(
        base_url=cred.base_url,
        api_key=cred.api_key,
        model=cred.model,
    )
