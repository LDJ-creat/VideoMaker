from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol


ProgressEmitter = Callable[[str], None]


def _noop_progress(_: str) -> None:
    return None


@dataclass(slots=True)
class RenderOptions:
    project_id: str
    generation_id: str
    timeline: dict[str, Any]
    storage_root: Path
    emit_progress: ProgressEmitter = _noop_progress
    aspect_ratio: str = "9:16"
    tts_mode: str | None = None


@dataclass(slots=True)
class RenderOutput:
    artifact_refs: list[dict[str, Any]] = field(default_factory=list)
    error: dict[str, Any] | None = None


class RenderBackend(Protocol):
    def render(self, options: RenderOptions) -> RenderOutput:
        ...
