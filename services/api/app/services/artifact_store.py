from __future__ import annotations

import uuid
from pathlib import Path

from app.db.session import Database
from app.services.task_events import now_iso


class ArtifactStore:
    def __init__(self, storage_root: Path) -> None:
        self.storage_root = storage_root.resolve()
        self.storage_root.mkdir(parents=True, exist_ok=True)

    def project_root(self, project_id: str) -> Path:
        root = self.storage_root / "projects" / project_id
        root.mkdir(parents=True, exist_ok=True)
        return root

    def resolve_project_path(self, project_id: str, relative_path: str) -> Path:
        root = self.project_root(project_id).resolve()
        resolved = (root / relative_path).resolve()
        if root != resolved and root not in resolved.parents:
            raise ValueError("artifact path resolves outside project storage")
        resolved.parent.mkdir(parents=True, exist_ok=True)
        return resolved

    def register_artifact(
        self,
        database: Database,
        *,
        project_id: str,
        task_id: str | None,
        artifact_type: str,
        relative_path: str,
    ) -> dict[str, str]:
        path = self.resolve_project_path(project_id, relative_path)
        artifact_id = str(uuid.uuid4())
        created_at = now_iso()
        uri = path.as_posix()

        with database.connect() as connection:
            connection.execute(
                """
                INSERT INTO artifacts (id, project_id, task_id, type, uri, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (artifact_id, project_id, task_id, artifact_type, uri, created_at),
            )

        return {
            "id": artifact_id,
            "type": artifact_type,
            "uri": uri,
            "createdAt": created_at,
        }
