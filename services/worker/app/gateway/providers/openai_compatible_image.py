from __future__ import annotations

import base64
import time
from typing import Any

import httpx

from urllib.parse import urlparse

from app.gateway.providers.base import GatewayError, ProviderConfig


def _is_dashscope_host(base_url: str) -> bool:
    return "dashscope" in base_url.lower()


def _dashscope_generation_url(base_url: str) -> str:
    parsed = urlparse(base_url)
    host = parsed.netloc.lower()
    scheme = parsed.scheme or "https"
    if "dashscope-intl" in host:
        api_host = "dashscope-intl.aliyuncs.com"
    elif "dashscope-us" in host:
        api_host = "dashscope-us.aliyuncs.com"
    else:
        api_host = "dashscope.aliyuncs.com"
    return f"{scheme}://{api_host}/api/v1/services/aigc/multimodal-generation/generation"


def _map_dashscope_size(size: Any) -> str:
    if isinstance(size, str):
        normalized = size.strip().upper()
        if normalized in {"1K", "2K", "4K"}:
            return normalized
    return "2K"


def _extract_image_bytes_from_dashscope(payload: dict[str, Any], client: httpx.Client) -> bytes:
    output = payload.get("output")
    if not isinstance(output, dict):
        raise GatewayError(
            code="invalid_response",
            message=f"Unexpected DashScope image response: {payload}",
            retryable=False,
        )
    choices = output.get("choices")
    if not isinstance(choices, list) or not choices:
        raise GatewayError(
            code="invalid_response",
            message=f"DashScope image response missing choices: {payload}",
            retryable=False,
        )
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, list):
        raise GatewayError(
            code="invalid_response",
            message=f"DashScope image response missing message content: {payload}",
            retryable=False,
        )
    for part in content:
        if not isinstance(part, dict):
            continue
        if part.get("type") == "image" and part.get("image"):
            image_ref = str(part["image"])
            if image_ref.startswith("http://") or image_ref.startswith("https://"):
                try:
                    download = client.get(image_ref)
                except httpx.HTTPError as exc:
                    raise GatewayError(
                        code="transport_error",
                        message=str(exc),
                        retryable=True,
                    ) from exc
                if download.status_code >= 400:
                    raise GatewayError(
                        code="http_error",
                        message=f"Failed to download DashScope image: HTTP {download.status_code}",
                        retryable=False,
                    )
                return download.content
            try:
                return base64.b64decode(image_ref)
            except (ValueError, TypeError) as exc:
                raise GatewayError(
                    code="invalid_response",
                    message="DashScope image content is not a URL or valid base64",
                    retryable=False,
                ) from exc
    raise GatewayError(
        code="invalid_response",
        message=f"DashScope image response missing image URL: {payload}",
        retryable=False,
    )


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
        use_dashscope = _is_dashscope_host(base)
        if use_dashscope:
            url = _dashscope_generation_url(base)
            body = {
                "model": model,
                "input": {
                    "messages": [
                        {
                            "role": "user",
                            "content": [{"text": prompt}],
                        }
                    ]
                },
                "parameters": {
                    "size": _map_dashscope_size(size),
                    "n": 1,
                    "watermark": False,
                },
            }
        else:
            url = f"{base}/images/generations"
            body = {
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
                if use_dashscope:
                    image_bytes = _extract_image_bytes_from_dashscope(payload, client)
                else:
                    item = payload["data"][0]
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
            except GatewayError:
                raise
            except (KeyError, IndexError, TypeError) as exc:
                raise GatewayError(
                    code="invalid_response",
                    message=f"Unexpected image generation response: {response.text}",
                    retryable=False,
                ) from exc

            self.last_latency_ms = int((time.perf_counter() - started) * 1000)
            return image_bytes
        finally:
            if owns_client:
                client.close()
