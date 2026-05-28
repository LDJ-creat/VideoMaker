from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.runtime.artifact_store import ArtifactStore


@dataclass
class TaskContext:
    project_id: str
    task_id: str
    storage_root: Path
    api_base_url: str | None = None
    artifacts: ArtifactStore = field(init=False)
    emitted_events: list[dict[str, Any]] = field(default_factory=list, init=False)
    artifact_refs: list[dict[str, Any]] = field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        self.artifacts = ArtifactStore(
            storage_root=Path(self.storage_root),
            project_id=self.project_id,
        )

    def emit_event(
        self,
        stage: str,
        progress: int,
        message: str,
        *,
        status: str = "running",
        error: dict[str, Any] | None = None,
        artifact_refs: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        event = {
            "taskId": self.task_id,
            "status": status,
            "stage": stage,
            "progress": progress,
            "message": message,
            "artifactRefs": artifact_refs or [],
            "error": error,
        }
        self.emitted_events.append(event)
        return event

    def register_artifact(self, artifact_type: str, path: str | Path) -> dict[str, Any]:
        ref = {
            "id": f"{self.task_id}-{len(self.artifact_refs) + 1}",
            "type": artifact_type,
            "uri": str(Path(path).resolve()),
        }
        self.artifact_refs.append(ref)
        return ref
