from __future__ import annotations

import threading
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Protocol

from app.gateway.model_gateway import ModelGateway
from app.runtime.video_gen_quota import VideoGenQuota

if TYPE_CHECKING:
    from app.agents.runner import AgentRunner
    from app.runtime.task_context import TaskContext

ProgressEmitter = Callable[[str, str], None]
ArtifactRegistrar = Callable[[str, str | Path], dict[str, Any]]
GatewayFactory = Callable[[], ModelGateway | Any]

MaterialResult = dict[str, Any]


class _LockedTaskContext:
    """Thread-safe facade for shared TaskContext during parallel material."""

    __slots__ = ("_inner", "_lock")

    def __init__(self, inner: TaskContext, lock: threading.Lock) -> None:
        self._inner = inner
        self._lock = lock

    def emit_event(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        with self._lock:
            return self._inner.emit_event(*args, **kwargs)

    def emit_progress(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        with self._lock:
            return self._inner.emit_progress(*args, **kwargs)

    def register_artifact(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        with self._lock:
            return self._inner.register_artifact(*args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


def resolve_storage_root(*, render_root: Path | None = None, generation_root: Path | None = None) -> Path:
    """Return the artifact storage root (parent of ``projects/``)."""
    if generation_root is not None:
        # storage/projects/{projectId}/generations/{generationId}
        return generation_root.parent.parent.parent.parent
    if render_root is not None:
        # storage/projects/{projectId}/renders/{generationId}
        return render_root.parent.parent.parent.parent
    raise ValueError("resolve_storage_root requires render_root or generation_root")


class _LockedVideoGenQuota:
    """Thread-safe facade over a shared VideoGenQuota."""

    def __init__(self, quota: VideoGenQuota, lock: threading.Lock) -> None:
        self._quota = quota
        self._lock = lock

    @property
    def used(self) -> int:
        with self._lock:
            return self._quota.used

    @property
    def max_calls(self) -> int:
        with self._lock:
            return self._quota.max_calls

    @property
    def remaining_slots(self) -> int:
        with self._lock:
            return self._quota.remaining_slots

    @property
    def remaining(self) -> int:
        with self._lock:
            return self._quota.remaining

    @property
    def max_per_slot(self) -> int:
        return self._quota.max_per_slot

    @property
    def max_slots(self) -> int:
        return self._quota.max_slots

    @property
    def consumed_slots(self) -> dict[str, int]:
        with self._lock:
            return dict(self._quota.consumed_slots)

    def has_video_quota(self) -> bool:
        with self._lock:
            return self._quota.has_video_quota()

    def can_generate_for_slot(self, slot_id: str) -> bool:
        with self._lock:
            return self._quota.can_generate_for_slot(slot_id)

    def consume(self, slot_id: str = "__legacy__") -> bool:
        with self._lock:
            return self._quota.consume(slot_id)

    def reserve(self, slot_id: str = "__legacy__") -> bool:
        with self._lock:
            return self._quota.reserve(slot_id)

    def release(self, slot_id: str = "__legacy__") -> None:
        with self._lock:
            self._quota.release(slot_id)

    def to_checkpoint(self) -> dict[str, Any]:
        with self._lock:
            return self._quota.to_checkpoint()


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
    narration_vo_profile: dict[str, Any] | None = None
    tts_directive_warning_emitted: bool = False
    visual_style_bible: dict[str, Any] | None = None
    packaging_plan: dict[str, Any] | None = None
    material_state_path: Path | None = None
    storage_root: Path | None = field(default=None, repr=False)
    sync_lock: threading.RLock = field(default_factory=threading.RLock, repr=False)
    gateway_factory: GatewayFactory | None = field(default=None, repr=False)
    cancel_event: threading.Event = field(default_factory=threading.Event, repr=False)

    def __post_init__(self) -> None:
        if self.storage_root is None:
            object.__setattr__(
                self,
                "storage_root",
                resolve_storage_root(render_root=self.render_root),
            )

    @property
    def project_root(self) -> Path:
        return self.render_root.parent.parent

    def is_cancelled(self) -> bool:
        return self.cancel_event.is_set()

    def request_cancel(self) -> None:
        self.cancel_event.set()

    def fork_for_slot(self) -> MaterialContext:
        lock = self.sync_lock
        base_emit = self.emit_progress
        base_register = self.register_artifact

        def locked_emit(stage: str, message: str) -> None:
            with lock:
                base_emit(stage, message)

        def locked_register(artifact_type: str, path: str | Path) -> dict[str, Any]:
            with lock:
                return base_register(artifact_type, path)

        new_gateway = self.gateway_factory() if self.gateway_factory is not None else self.gateway
        locked_quota = _LockedVideoGenQuota(self.quota, lock)
        task_context = self.task_context
        if task_context is not None:
            task_context = _LockedTaskContext(task_context, lock)  # type: ignore[assignment]
        slot_ctx = replace(
            self,
            gateway=new_gateway,
            quota=locked_quota,  # type: ignore[arg-type]
            emit_progress=locked_emit,
            register_artifact=locked_register,
            providers={},
            sync_lock=lock,
            task_context=task_context,
            cancel_event=self.cancel_event,
        )
        return slot_ctx


class CompletionStrategyProvider(Protocol):
    name: str

    def execute(self, action: dict[str, Any], ctx: MaterialContext) -> MaterialResult: ...
