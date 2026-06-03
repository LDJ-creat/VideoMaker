"""Shared types for pluggable video providers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class VideoJobResult:
    status: str
    job_id: str
    video_bytes: bytes | None = None
    latency_ms: int | None = None


class VideoProvider(Protocol):
    def submit(self, prompt: str, options: dict[str, Any]) -> str: ...

    def poll(self, job_id: str) -> VideoJobResult: ...
