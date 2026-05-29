from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol

from app.gateway.model_gateway import ModelGateway
from app.runtime.video_gen_quota import VideoGenQuota

ProgressEmitter = Callable[[str, str], None]
ArtifactRegistrar = Callable[[str, str | Path], dict[str, Any]]

MaterialResult = dict[str, Any]


@dataclass
class MaterialContext:
    project_id: str
    generation_id: str
    render_root: Path
    generated_root: Path
    gateway: ModelGateway
    quota: VideoGenQuota
    inventory: dict[str, Any]
    slot_matches: list[dict[str, Any]]
    storyboard: list[dict[str, Any]]
    structure: dict[str, Any]
    emit_progress: ProgressEmitter
    register_artifact: ArtifactRegistrar
    completed_action_ids: set[str] = field(default_factory=set)
    providers: dict[str, CompletionStrategyProvider] = field(default_factory=dict)


class CompletionStrategyProvider(Protocol):
    name: str

    def execute(self, action: dict[str, Any], ctx: MaterialContext) -> MaterialResult: ...
