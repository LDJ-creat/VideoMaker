from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Protocol

from app.gateway.model_gateway import ModelGateway
from app.runtime.video_gen_quota import VideoGenQuota

if TYPE_CHECKING:
    from app.agents.runner import AgentRunner
    from app.runtime.task_context import TaskContext

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
    runner: AgentRunner | None = None
    task_context: TaskContext | None = None
    variant_overrides: dict[str, Any] = field(default_factory=dict)
    brand_colors: dict[str, Any] = field(default_factory=dict)
    aspect_ratio: str = "9:16"
    master_narration: str = ""
    visual_style_bible: dict[str, Any] | None = None
    packaging_plan: dict[str, Any] | None = None

    @property
    def project_root(self) -> Path:
        return self.render_root.parent.parent


class CompletionStrategyProvider(Protocol):
    name: str

    def execute(self, action: dict[str, Any], ctx: MaterialContext) -> MaterialResult: ...
