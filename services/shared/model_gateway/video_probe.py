from __future__ import annotations

import time
from typing import Any

import httpx

from model_gateway.chat_endpoint import resolve_chat_completions_url
from model_gateway.text_probe import TextProbeResult, _truncate

_PROBE_PROMPT = (
    "You are a connectivity probe. Reply with exactly: OK"
)


def probe_video_understanding_chat(
    *,
    base_url: str,
    api_key: str,
    model: str,
    timeout_sec: float = 45.0,
    client: httpx.Client | None = None,
) -> TextProbeResult:
    """Probe videoUnderstanding provider via the same Ark/OpenAI chat endpoint."""
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
        "max_tokens": 16,
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
        except (KeyError, IndexError, TypeError, ValueError):
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
            message="视频理解连接成功",
            reply_preview=preview,
        )
    finally:
        if owns_client:
            http_client.close()
