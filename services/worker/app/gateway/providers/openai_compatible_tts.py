from __future__ import annotations

import time
from typing import Any

import httpx

from app.gateway.providers.base import GatewayError, ProviderConfig


class OpenAICompatibleTTSProvider:
    def __init__(
        self,
        config: ProviderConfig,
        *,
        client: httpx.Client | None = None,
        timeout_sec: float = 60.0,
    ) -> None:
        self.config = config
        self._client = client
        self._timeout_sec = timeout_sec
        self.last_latency_ms: int | None = None

    def _get_client(self) -> httpx.Client:
        if self._client is not None:
            return self._client
        return httpx.Client(timeout=self._timeout_sec)

    def synthesize(self, text: str, *, options: dict[str, Any] | None = None) -> bytes:
        if not self.config.api_key:
            raise GatewayError(
                code="missing_api_key",
                message="TTS provider API key is not configured",
                retryable=False,
            )

        opts = options or {}
        voice = str(opts.get("voice", "alloy"))
        model = str(opts.get("model", self.config.model))

        base = self.config.base_url.rstrip("/")
        url = f"{base}/audio/speech"
        body = {"model": model, "input": text, "voice": voice}
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

        started = time.perf_counter()
        owns_client = self._client is None
        client = self._get_client()
        try:
            try:
                response = client.post(url, headers=headers, json=body)
            except httpx.HTTPError as exc:
                raise GatewayError(
                    code="transport_error",
                    message=str(exc),
                    retryable=True,
                ) from exc

            if response.status_code >= 400:
                raise GatewayError(
                    code="http_error",
                    message=f"HTTP {response.status_code}: {response.text}",
                    retryable=response.status_code in {429, 502, 503},
                )

            self.last_latency_ms = int((time.perf_counter() - started) * 1000)
            return response.content
        finally:
            if owns_client:
                client.close()
