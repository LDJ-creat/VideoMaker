"""Volcengine Ark SeedDance 2.0 text-to-video and image-to-video (async task API)."""

from __future__ import annotations

import base64
import os
import time
from pathlib import Path
from typing import Any

import httpx

from model_gateway.video_driver import (
    DEFAULT_SEEDDANCE_MODEL,
    map_seeddance_duration,
    map_seeddance_ratio,
    map_seeddance_resolution,
)
from app.gateway.providers.base import GatewayError, ProviderConfig
from app.gateway.providers.video_types import VideoJobResult, VideoProvider

_PENDING_STATUSES = frozenset({"queued", "running", "pending", ""})
_TERMINAL_FAILURE_STATUSES = frozenset({"failed", "expired", "cancelled", "canceled"})


def _tasks_url(base_url: str) -> str:
    return f"{base_url.rstrip('/')}/contents/generations/tasks"


def _task_url(base_url: str, task_id: str) -> str:
    return f"{_tasks_url(base_url)}/{task_id}"


def _encode_reference_image(path: Path) -> str:
    resolved = path.resolve()
    if not resolved.is_file():
        raise GatewayError(
            code="missing_reference_image",
            message=f"Reference image not found: {resolved}",
            retryable=False,
        )
    raw = resolved.read_bytes()
    suffix = resolved.suffix.lower()
    mime = "image/png"
    if suffix in {".jpg", ".jpeg"}:
        mime = "image/jpeg"
    elif suffix == ".webp":
        mime = "image/webp"
    encoded = base64.b64encode(raw).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _resolve_model(config: ProviderConfig) -> str:
    return (config.model or "").strip() or DEFAULT_SEEDDANCE_MODEL


def _build_submit_body(
    prompt: str,
    *,
    model: str,
    options: dict[str, Any],
) -> dict[str, Any]:
    mode = str(options.get("mode", "t2v")).lower()
    duration = map_seeddance_duration(float(options.get("durationSec", 5)))
    resolution = map_seeddance_resolution(
        str(options.get("resolution") or os.getenv("VIDEO_DEFAULT_RESOLUTION", "720P"))
    )

    content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
    ratio = map_seeddance_ratio(str(options.get("aspectRatio") or "16:9"))

    ref_path = options.get("referenceImagePath")
    if mode == "i2v" and ref_path:
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": _encode_reference_image(Path(str(ref_path)))},
            }
        )
        ratio = "adaptive"

    return {
        "model": model,
        "content": content,
        "resolution": resolution,
        "ratio": ratio,
        "duration": duration,
        "watermark": False,
    }


def _extract_video_url(payload: dict[str, Any]) -> str | None:
    content = payload.get("content")
    if isinstance(content, dict):
        for key in ("video_url", "videoUrl", "url"):
            value = content.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    output = payload.get("output")
    if isinstance(output, dict):
        for key in ("video_url", "videoUrl", "url"):
            value = output.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    for key in ("video_url", "videoUrl"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _task_status(payload: dict[str, Any]) -> str:
    status = payload.get("status")
    if isinstance(status, str) and status.strip():
        return status.strip().lower()
    output = payload.get("output")
    if isinstance(output, dict):
        nested = output.get("status") or output.get("task_status")
        if isinstance(nested, str) and nested.strip():
            return nested.strip().lower()
    return ""


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return max(0, int(raw))
    except ValueError:
        return default


class VolcengineSeedDanceVideoProvider:
    def __init__(
        self,
        config: ProviderConfig,
        *,
        client: httpx.Client | None = None,
        poll_interval_sec: float = 15.0,
        max_poll_sec: int | None = None,
    ) -> None:
        self.config = config
        self._client = client
        self.poll_interval_sec = poll_interval_sec
        self.max_poll_sec = max_poll_sec or _env_int("VIDEO_MAX_POLL_SEC", 600)
        self.last_latency_ms: int | None = None

    def _get_client(self) -> httpx.Client:
        if self._client is not None:
            return self._client
        return httpx.Client(timeout=180.0)

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        return headers

    def submit(self, prompt: str, options: dict[str, Any]) -> str:
        if not self.config.base_url:
            raise GatewayError(
                code="missing_config",
                message="Video API base URL is not configured",
                retryable=False,
            )
        url = _tasks_url(self.config.base_url)
        body = _build_submit_body(prompt, model=_resolve_model(self.config), options=options)

        owns_client = self._client is None
        client = self._get_client()
        try:
            try:
                response = client.post(url, headers=self._headers(), json=body)
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
            except ValueError as exc:
                raise GatewayError(
                    code="invalid_response",
                    message=f"Unexpected SeedDance submit response: {response.text}",
                    retryable=False,
                ) from exc

            task_id = payload.get("id") or payload.get("task_id") or payload.get("taskId")
            if not isinstance(task_id, str) or not task_id:
                raise GatewayError(
                    code="invalid_response",
                    message=f"SeedDance submit missing task id: {response.text}",
                    retryable=False,
                )
            return task_id
        finally:
            if owns_client:
                client.close()

    def poll(self, job_id: str) -> VideoJobResult:
        if not self.config.base_url:
            raise GatewayError(
                code="missing_config",
                message="Video API base URL is not configured",
                retryable=False,
            )

        url = _task_url(self.config.base_url, job_id)
        started = time.perf_counter()
        deadline = started + self.max_poll_sec
        owns_client = self._client is None
        client = self._get_client()
        try:
            while True:
                try:
                    response = client.get(url, headers=self._headers())
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
                except ValueError as exc:
                    raise GatewayError(
                        code="invalid_response",
                        message=f"Unexpected SeedDance poll response: {response.text}",
                        retryable=False,
                    ) from exc

                status = _task_status(payload)

                if status in _PENDING_STATUSES:
                    if time.perf_counter() >= deadline:
                        raise GatewayError(
                            code="poll_timeout",
                            message=f"Video task {job_id} did not complete within {self.max_poll_sec}s",
                            retryable=True,
                        )
                    time.sleep(self.poll_interval_sec)
                    continue

                if status in _TERMINAL_FAILURE_STATUSES:
                    message = ""
                    if isinstance(payload.get("error"), dict):
                        message = str(payload["error"].get("message", ""))
                    raise GatewayError(
                        code="video_job_failed",
                        message=message or f"SeedDance video task {job_id} failed",
                        retryable=False,
                    )

                video_bytes: bytes | None = None
                video_url = _extract_video_url(payload)
                if status == "succeeded" and video_url:
                    try:
                        download = client.get(video_url)
                    except httpx.HTTPError as exc:
                        raise GatewayError(
                            code="transport_error",
                            message=str(exc),
                            retryable=True,
                        ) from exc
                    if download.status_code >= 400:
                        raise GatewayError(
                            code="http_error",
                            message=f"Failed to download video: HTTP {download.status_code}",
                            retryable=False,
                        )
                    video_bytes = download.content

                self.last_latency_ms = int((time.perf_counter() - started) * 1000)
                return VideoJobResult(
                    status="succeeded" if video_bytes else status or "unknown",
                    job_id=job_id,
                    video_bytes=video_bytes,
                    latency_ms=self.last_latency_ms,
                )
        finally:
            if owns_client:
                client.close()
