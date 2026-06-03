"""DashScope Wan text-to-video and image-to-video (async task API)."""

from __future__ import annotations

import base64
import os
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from model_gateway.video_driver import (
    DEFAULT_DASHSCOPE_I2V_MODEL,
    DEFAULT_DASHSCOPE_T2V_MODEL,
    normalize_wan_model_for_mode,
)
from app.gateway.providers.base import GatewayError, ProviderConfig
from app.gateway.providers.video_types import VideoJobResult, VideoProvider

WAN_DURATION_STEPS = (5, 10, 15)
DEFAULT_T2V_MODEL = DEFAULT_DASHSCOPE_T2V_MODEL
DEFAULT_I2V_MODEL = DEFAULT_DASHSCOPE_I2V_MODEL

_WAN_SIZE_BY_TIER = {
    "480P": "832*480",
    "720P": "1280*720",
    "1080P": "1920*1080",
}


def _default_wan_model(mode: str, explicit_model: str | None) -> str:
    return normalize_wan_model_for_mode(explicit_model or "", mode=mode)


def _wan_submit_parameters(
    *,
    model: str,
    mode: str,
    duration: int,
    resolution: str,
) -> dict[str, Any]:
    model_lower = model.lower()
    if model_lower.startswith("wan2.6") and mode == "t2v":
        tier = resolution.upper() if resolution else "720P"
        return {
            "duration": duration,
            "size": _WAN_SIZE_BY_TIER.get(tier, "1280*720"),
            "prompt_extend": True,
        }
    return {
        "duration": duration,
        "resolution": resolution,
        "prompt_extend": True,
    }


def _is_dashscope_host(base_url: str) -> bool:
    return "dashscope" in base_url.lower()


def _dashscope_api_host(base_url: str) -> str:
    parsed = urlparse(base_url)
    host = parsed.netloc.lower()
    scheme = parsed.scheme or "https"
    if "dashscope-intl" in host:
        return f"{scheme}://dashscope-intl.aliyuncs.com"
    if "dashscope-us" in host:
        return f"{scheme}://dashscope-us.aliyuncs.com"
    return f"{scheme}://dashscope.aliyuncs.com"


def _video_synthesis_url(base_url: str) -> str:
    return f"{_dashscope_api_host(base_url)}/api/v1/services/aigc/video-generation/video-synthesis"


def _task_url(base_url: str, task_id: str) -> str:
    return f"{_dashscope_api_host(base_url)}/api/v1/tasks/{task_id}"


def map_wan_duration(duration_sec: float) -> int:
    """Map storyboard duration to Wan-supported discrete seconds."""
    if duration_sec <= 0:
        return 5
    target = int(duration_sec + 0.999)
    for step in WAN_DURATION_STEPS:
        if target <= step:
            return step
    return WAN_DURATION_STEPS[-1]


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


def _build_submit_body(
    prompt: str,
    *,
    model: str | None,
    options: dict[str, Any],
) -> dict[str, Any]:
    mode = str(options.get("mode", "t2v")).lower()
    duration = map_wan_duration(float(options.get("durationSec", 5)))
    resolution = str(options.get("resolution") or os.getenv("VIDEO_DEFAULT_RESOLUTION", "720P"))

    input_payload: dict[str, Any] = {"prompt": prompt}
    ref_path = options.get("referenceImagePath")
    if mode == "i2v" and ref_path:
        input_payload["img_url"] = _encode_reference_image(Path(str(ref_path)))

    body: dict[str, Any] = {
        "model": _default_wan_model(mode, model),
        "input": input_payload,
        "parameters": _wan_submit_parameters(
            model=_default_wan_model(mode, model),
            mode=mode,
            duration=duration,
            resolution=resolution,
        ),
    }
    return body


def _extract_video_url(payload: dict[str, Any]) -> str | None:
    output = payload.get("output")
    if not isinstance(output, dict):
        return None
    for key in ("video_url", "videoUrl", "url"):
        value = output.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    results = output.get("results")
    if isinstance(results, list) and results:
        first = results[0]
        if isinstance(first, dict):
            for key in ("url", "video_url"):
                value = first.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
    return None


def _task_status(payload: dict[str, Any]) -> str:
    output = payload.get("output")
    if isinstance(output, dict) and output.get("task_status"):
        return str(output["task_status"]).upper()
    if payload.get("task_status"):
        return str(payload["task_status"]).upper()
    return str(payload.get("status", "")).upper()


class DashScopeWanVideoProvider:
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
        headers = {
            "Content-Type": "application/json",
            "X-DashScope-Async": "enable",
        }
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
        url = _video_synthesis_url(self.config.base_url)
        body = _build_submit_body(prompt, model=self.config.model, options=options)

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

            payload = response.json()
            output = payload.get("output") if isinstance(payload, dict) else None
            task_id = None
            if isinstance(output, dict):
                task_id = output.get("task_id") or output.get("taskId")
            if not task_id and isinstance(payload, dict):
                task_id = payload.get("task_id") or payload.get("taskId")
            if not isinstance(task_id, str) or not task_id:
                raise GatewayError(
                    code="invalid_response",
                    message=f"DashScope video submit missing task_id: {response.text}",
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

                payload = response.json()
                status = _task_status(payload)

                if status in {"PENDING", "RUNNING", "QUEUED", ""}:
                    if time.perf_counter() >= deadline:
                        raise GatewayError(
                            code="poll_timeout",
                            message=f"Video task {job_id} did not complete within {self.max_poll_sec}s",
                            retryable=True,
                        )
                    time.sleep(self.poll_interval_sec)
                    continue

                if status in {"FAILED", "CANCELED", "CANCELLED"}:
                    message = ""
                    if isinstance(payload.get("output"), dict):
                        message = str(payload["output"].get("message", ""))
                    raise GatewayError(
                        code="video_job_failed",
                        message=message or f"DashScope video task {job_id} failed",
                        retryable=False,
                    )

                video_bytes: bytes | None = None
                video_url = _extract_video_url(payload)
                if video_url:
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
                    status="succeeded" if video_bytes else status.lower(),
                    job_id=job_id,
                    video_bytes=video_bytes,
                    latency_ms=self.last_latency_ms,
                )
        finally:
            if owns_client:
                client.close()


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return max(0, int(raw))
    except ValueError:
        return default


def resolve_video_driver(driver: str, base_url: str) -> str:
    from model_gateway.video_driver import resolve_effective_video_driver

    return resolve_effective_video_driver(driver, base_url)
