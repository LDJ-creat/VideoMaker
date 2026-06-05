from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import httpx

from model_gateway.chat_endpoint import resolve_chat_completions_url

_PROBE_PROMPT = "Reply with exactly: OK"
_PROBE_MAX_TOKENS = 16


@dataclass(frozen=True)
class TextProbeResult:
    ok: bool
    latency_ms: int
    message: str
    detail: str | None = None
    reply_preview: str | None = None


def _truncate(text: str, limit: int = 120) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[: limit - 1]}…"


def probe_text_chat(
    *,
    base_url: str,
    api_key: str,
    model: str,
    timeout_sec: float = 30.0,
    client: httpx.Client | None = None,
) -> TextProbeResult:
    """Minimal OpenAI-compatible chat probe for text provider connectivity."""
    started = time.perf_counter()

    if not base_url.strip():
        return TextProbeResult(
            ok=False,
            latency_ms=0,
            message="Base URL 未配置",
            detail="base_url_empty",
        )
    if not model.strip():
        return TextProbeResult(
            ok=False,
            latency_ms=0,
            message="Model 未配置",
            detail="model_empty",
        )
    if not api_key.strip():
        return TextProbeResult(
            ok=False,
            latency_ms=0,
            message="API Key 未配置",
            detail="missing_api_key",
        )

    url = resolve_chat_completions_url(base_url.strip())
    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
        "Content-Type": "application/json",
    }
    body: dict[str, Any] = {
        "model": model.strip(),
        "messages": [{"role": "user", "content": _PROBE_PROMPT}],
        "max_tokens": _PROBE_MAX_TOKENS,
        "temperature": 0,
    }

    owns_client = client is None
    http_client = client or httpx.Client(timeout=timeout_sec)
    try:
        try:
            response = http_client.post(url, headers=headers, json=body)
        except httpx.HTTPError as exc:
            latency_ms = int((time.perf_counter() - started) * 1000)
            return TextProbeResult(
                ok=False,
                latency_ms=latency_ms,
                message="网络请求失败",
                detail=str(exc),
            )

        latency_ms = int((time.perf_counter() - started) * 1000)
        if response.status_code >= 400:
            return TextProbeResult(
                ok=False,
                latency_ms=latency_ms,
                message=f"HTTP {response.status_code}",
                detail=_truncate(response.text),
            )

        try:
            payload = response.json()
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            return TextProbeResult(
                ok=False,
                latency_ms=latency_ms,
                message="响应格式异常",
                detail=_truncate(response.text),
            )

        if not isinstance(content, str) or not content.strip():
            return TextProbeResult(
                ok=False,
                latency_ms=latency_ms,
                message="模型返回空内容",
                detail=_truncate(response.text),
            )

        preview = _truncate(content.strip())
        return TextProbeResult(
            ok=True,
            latency_ms=latency_ms,
            message="连接成功",
            reply_preview=preview,
        )
    finally:
        if owns_client:
            http_client.close()
