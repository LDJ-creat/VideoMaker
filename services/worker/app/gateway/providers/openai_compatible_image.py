from __future__ import annotations

import base64
import time
from typing import Any

import httpx

from app.gateway.providers.base import GatewayError, ProviderConfig


class OpenAICompatibleImageProvider:
    def __init__(
        self,
        config: ProviderConfig,
        *,
        client: httpx.Client | None = None,
        timeout_sec: float = 120.0,
    ) -> None:
        self.config = config
        self._client = client
        self._timeout_sec = timeout_sec
        self.last_latency_ms: int | None = None

    def _get_client(self) -> httpx.Client:
        if self._client is not None:
            return self._client
        return httpx.Client(timeout=self._timeout_sec)

    def generate(self, prompt: str, *, options: dict[str, Any] | None = None) -> bytes:
        if not self.config.api_key:
            raise GatewayError(
                code="missing_api_key",
                message="Image provider API key is not configured",
                retryable=False,
            )

        opts = options or {}
        model = str(opts.get("model", self.config.model))
        size = opts.get("size", "1024x1024")

        base = self.config.base_url.rstrip("/")
        url = f"{base}/images/generations"
        body: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "size": size,
            "n": 1,
        }
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

            try:
                payload = response.json()
                item = payload["data"][0]
            except (KeyError, IndexError) as exc:
                raise GatewayError(
                    code="invalid_response",
                    message=f"Unexpected image generation response: {response.text}",
                    retryable=False,
                ) from exc

            if "b64_json" in item:
                image_bytes = base64.b64decode(item["b64_json"])
            elif "url" in item:
                try:
                    download = client.get(item["url"])
                except httpx.HTTPError as exc:
                    raise GatewayError(
                        code="transport_error",
                        message=str(exc),
                        retryable=True,
                    ) from exc
                if download.status_code >= 400:
                    raise GatewayError(
                        code="http_error",
                        message=f"Failed to download image: HTTP {download.status_code}",
                        retryable=False,
                    )
                image_bytes = download.content
            else:
                raise GatewayError(
                    code="invalid_response",
                    message="Image response missing b64_json or url",
                    retryable=False,
                )

            self.last_latency_ms = int((time.perf_counter() - started) * 1000)
            return image_bytes
        finally:
            if owns_client:
                client.close()
