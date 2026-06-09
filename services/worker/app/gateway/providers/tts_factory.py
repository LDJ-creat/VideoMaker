from __future__ import annotations

from typing import Any, Protocol

import httpx

from app.gateway.providers.base import ProviderConfig
from app.gateway.providers.openai_compatible_tts import OpenAICompatibleTTSProvider
from app.gateway.providers.volcengine_tts import VolcengineTTSProvider

try:
    from model_gateway.tts_driver import resolve_effective_tts_driver
except ImportError:  # pragma: no cover

    def resolve_effective_tts_driver(driver: str) -> str:
        return (driver or "openai_compatible").strip().lower()


class TTSProviderProtocol(Protocol):
    last_latency_ms: int | None

    def synthesize(self, text: str, *, options: dict[str, Any] | None = None) -> bytes: ...


def create_tts_provider(
    driver: str,
    config: ProviderConfig,
    *,
    tts_preferences: dict[str, Any],
    client: httpx.Client | None = None,
) -> TTSProviderProtocol:
    effective = resolve_effective_tts_driver(driver)
    if effective == "volcengine_tts":
        return VolcengineTTSProvider(
            config,
            preferences=tts_preferences,
            client=client,
        )
    return OpenAICompatibleTTSProvider(config, client=client)
