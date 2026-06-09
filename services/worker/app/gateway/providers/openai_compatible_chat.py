from __future__ import annotations

import json
import time
from typing import Any

import httpx

from model_gateway.chat_endpoint import resolve_chat_completions_url
from app.gateway.providers.base import GatewayError, ProviderConfig

_RETRYABLE_STATUS = {429, 502, 503}
_RETRY_DELAYS_SEC = (0.5, 1.0)


class OpenAICompatibleChatProvider:
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

    def complete_assistant_message(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str | None = None,
        response_format: dict[str, str] | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self.config.api_key:
            raise GatewayError(
                code="missing_api_key",
                message="Chat provider API key is not configured",
                retryable=False,
            )

        base = self.config.base_url.rstrip("/")
        url = resolve_chat_completions_url(base)
        body: dict[str, Any] = {
            "model": model or self.config.model,
            "messages": messages,
        }
        if response_format is not None:
            body["response_format"] = response_format
        if tools is not None:
            body["tools"] = tools
        if tool_choice is not None:
            body["tool_choice"] = tool_choice
        body["max_tokens"] = 16384

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

        started = time.perf_counter()
        last_error: GatewayError | None = None
        owns_client = self._client is None
        client = self._get_client()
        try:
            for attempt in range(len(_RETRY_DELAYS_SEC) + 1):
                try:
                    response = client.post(url, headers=headers, json=body)
                except httpx.HTTPError as exc:
                    last_error = GatewayError(
                        code="transport_error",
                        message=str(exc),
                        retryable=True,
                    )
                    if attempt < len(_RETRY_DELAYS_SEC):
                        time.sleep(_RETRY_DELAYS_SEC[attempt])
                        continue
                    raise last_error

                if response.status_code in _RETRYABLE_STATUS:
                    last_error = GatewayError(
                        code="rate_limit" if response.status_code == 429 else "upstream_error",
                        message=f"HTTP {response.status_code}: {response.text}",
                        retryable=True,
                    )
                    if attempt < len(_RETRY_DELAYS_SEC):
                        time.sleep(_RETRY_DELAYS_SEC[attempt])
                        continue
                    raise last_error

                if response.status_code >= 400:
                    raise GatewayError(
                        code="http_error",
                        message=f"HTTP {response.status_code}: {response.text}",
                        retryable=False,
                    )

                try:
                    payload = response.json()
                    message = payload["choices"][0]["message"]
                except (KeyError, IndexError, json.JSONDecodeError) as exc:
                    raise GatewayError(
                        code="invalid_response",
                        message=f"Unexpected chat completion response: {response.text}",
                        retryable=False,
                    ) from exc

                if not isinstance(message, dict):
                    raise GatewayError(
                        code="invalid_response",
                        message="Chat completion message is not an object",
                        retryable=False,
                    )

                self.last_latency_ms = int((time.perf_counter() - started) * 1000)
                return message

            if last_error is not None:
                raise last_error
            raise GatewayError(
                code="unknown_error",
                message="Chat completion failed without response",
                retryable=False,
            )
        finally:
            if owns_client:
                client.close()

    def complete(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str | None = None,
        response_format: dict[str, str] | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> str:
        message = self.complete_assistant_message(
            messages,
            model=model,
            response_format=response_format,
            tools=tools,
            tool_choice=tool_choice,
        )
        content = message.get("content")
        if not isinstance(content, str):
            raise GatewayError(
                code="invalid_response",
                message="Chat completion content is not a string",
                retryable=False,
            )
        return content
