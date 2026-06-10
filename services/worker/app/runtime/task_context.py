from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
from urllib import request

from app.runtime.artifact_store import ArtifactStore


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass
class TaskContext:
    project_id: str
    task_id: str
    storage_root: Path
    api_base_url: str | None = None
    event_publisher: Any | None = None
    artifacts: ArtifactStore = field(init=False)
    emitted_events: list[dict[str, Any]] = field(default_factory=list, init=False)
    artifact_refs: list[dict[str, Any]] = field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        self.artifacts = ArtifactStore(
            storage_root=Path(self.storage_root),
            project_id=self.project_id,
        )
        if self.event_publisher is None and self.api_base_url:
            self.event_publisher = self._publish_event_to_api

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
            "artifactRefs": artifact_refs or list(self.artifact_refs),
            "error": error,
            "updatedAt": _utc_now_iso(),
        }
        self.emitted_events.append(event)
        if self.event_publisher is not None:
            self.event_publisher(event)
        return event

    def emit_progress(
        self,
        stage: str,
        message: str,
        *,
        progress: int | None = None,
    ) -> dict[str, Any]:
        """Emit a stage/message update; reuses the last progress when omitted."""
        resolved = progress
        if resolved is None and self.emitted_events:
            resolved = int(self.emitted_events[-1].get("progress", 0))
        if resolved is None:
            resolved = 0
        return self.emit_event(stage=stage, progress=resolved, message=message)

    def register_artifact(self, artifact_type: str, path: str | Path) -> dict[str, Any]:
        ref = {
            "id": f"{self.task_id}-{len(self.artifact_refs) + 1}",
            "type": artifact_type,
            "uri": str(Path(path).resolve()),
            "createdAt": _utc_now_iso(),
        }
        self.artifact_refs.append(ref)
        return ref

    def _publish_event_to_api(self, event: dict[str, Any]) -> None:
        if not self.api_base_url:
            return
        endpoint = self.api_base_url.rstrip("/") + f"/api/tasks/{self.task_id}/events"
        payload = json.dumps(event).encode("utf-8")
        request_payload = request.Request(
            endpoint,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(request_payload, timeout=3):
                pass
        except Exception:
            # Event sink is best-effort; pipeline artifacts remain authoritative.
            return
