"""Pluggable video job adapter.

Drivers:
- ``dashscope_wan``: DashScope Wan video-synthesis + task poll (auto when base URL contains ``dashscope``)
- ``generic_job``: ``POST /videos`` job API for custom gateways

Environment:
- ``VIDEO_DRIVER=dashscope_wan|generic_job`` (optional override)
- ``VIDEO_MAX_POLL_SEC`` async poll timeout

``generic_job`` body includes ``prompt`` plus options such as ``mode``, ``referenceImagePath``, ``durationSec``.
"""

from __future__ import annotations

import time
from typing import Any

import httpx

from app.gateway.providers.base import GatewayError, ProviderConfig
from app.gateway.providers.video_types import VideoJobResult, VideoProvider


class GenericJobVideoProvider:
    def __init__(
        self,
        config: ProviderConfig,
        *,
        client: httpx.Client | None = None,
        poll_interval_sec: float = 3.0,
        max_poll_sec: int = 300,
    ) -> None:
        self.config = config
        self._client = client
        self.poll_interval_sec = poll_interval_sec
        self.max_poll_sec = max_poll_sec
        self.last_latency_ms: int | None = None

    def _get_client(self) -> httpx.Client:
        if self._client is not None:
            return self._client
        return httpx.Client(timeout=120.0)

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

        base = self.config.base_url.rstrip("/")
        url = f"{base}/videos"
        body: dict[str, Any] = {"prompt": prompt, **options}
        if self.config.model:
            body.setdefault("model", self.config.model)

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
                job_id = response.json()["jobId"]
            except (KeyError, ValueError) as exc:
                raise GatewayError(
                    code="invalid_response",
                    message=f"Unexpected video submit response: {response.text}",
                    retryable=False,
                ) from exc

            if not isinstance(job_id, str) or not job_id:
                raise GatewayError(
                    code="invalid_response",
                    message="Video submit response jobId must be a non-empty string",
                    retryable=False,
                )
            return job_id
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

        base = self.config.base_url.rstrip("/")
        url = f"{base}/videos/{job_id}"
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
                    status = str(payload["status"]).lower()
                except (KeyError, ValueError) as exc:
                    raise GatewayError(
                        code="invalid_response",
                        message=f"Unexpected video poll response: {response.text}",
                        retryable=False,
                    ) from exc

                if status == "pending":
                    if time.perf_counter() >= deadline:
                        raise GatewayError(
                            code="poll_timeout",
                            message=f"Video job {job_id} did not complete within {self.max_poll_sec}s",
                            retryable=True,
                        )
                    time.sleep(self.poll_interval_sec)
                    continue

                video_bytes: bytes | None = None
                download_url = payload.get("downloadUrl")
                if status == "succeeded" and download_url:
                    try:
                        download = client.get(download_url)
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
                    status=status,
                    job_id=job_id,
                    video_bytes=video_bytes,
                    latency_ms=self.last_latency_ms,
                )
        finally:
            if owns_client:
                client.close()


def create_video_provider(
    driver: str,
    config: ProviderConfig,
    *,
    client: httpx.Client | None = None,
    poll_interval_sec: float = 3.0,
    max_poll_sec: int = 300,
) -> VideoProvider:
    from app.gateway.providers.dashscope_video import (
        DashScopeWanVideoProvider,
        resolve_video_driver,
    )

    resolved = resolve_video_driver(driver, config.base_url or "")
    if resolved == "dashscope_wan":
        return DashScopeWanVideoProvider(
            config,
            client=client,
            poll_interval_sec=max(poll_interval_sec, 15.0),
            max_poll_sec=max_poll_sec,
        )
    if resolved == "generic_job":
        return GenericJobVideoProvider(
            config,
            client=client,
            poll_interval_sec=poll_interval_sec,
            max_poll_sec=max_poll_sec,
        )
    raise GatewayError(
        code="unsupported_driver",
        message=f"Unsupported VIDEO_DRIVER: {driver}",
        retryable=False,
    )
