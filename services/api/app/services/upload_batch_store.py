from __future__ import annotations

import json
import uuid
from typing import Any

from app.db.session import Database
from app.services.task_events import now_iso


class UploadBatchStore:
    def __init__(self, database: Database) -> None:
        self.database = database

    def create_batch(self, *, project_id: str, status: str = "uploading") -> dict[str, Any]:
        batch_id = str(uuid.uuid4())
        created_at = now_iso()
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO upload_batches (
                  id, project_id, status, sample_ids_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (batch_id, project_id, status, "[]", created_at, created_at),
            )
        return {
            "id": batch_id,
            "projectId": project_id,
            "status": status,
            "sampleIds": [],
            "createdAt": created_at,
            "updatedAt": created_at,
        }

    def get_batch(self, batch_id: str) -> dict[str, Any] | None:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT id, project_id, status, sample_ids_json, created_at, updated_at
                FROM upload_batches WHERE id = ?
                """,
                (batch_id,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_batch(row)

    def list_batches(self, project_id: str) -> list[dict[str, Any]]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT id, project_id, status, sample_ids_json, created_at, updated_at
                FROM upload_batches
                WHERE project_id = ?
                ORDER BY created_at DESC
                """,
                (project_id,),
            ).fetchall()
        return [self._row_to_batch(row) for row in rows]

    def add_sample_to_batch(self, batch_id: str, sample_id: str) -> dict[str, Any]:
        batch = self.get_batch(batch_id)
        if batch is None:
            raise ValueError(f"Upload batch not found: {batch_id}")
        sample_ids = list(batch["sampleIds"])
        if sample_id not in sample_ids:
            sample_ids.append(sample_id)
        updated_at = now_iso()
        with self.database.connect() as connection:
            connection.execute(
                """
                UPDATE upload_batches
                SET sample_ids_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (json.dumps(sample_ids, separators=(",", ":")), updated_at, batch_id),
            )
        batch["sampleIds"] = sample_ids
        batch["updatedAt"] = updated_at
        return batch

    def update_batch_status(self, batch_id: str, *, status: str) -> dict[str, Any]:
        updated_at = now_iso()
        with self.database.connect() as connection:
            connection.execute(
                "UPDATE upload_batches SET status = ?, updated_at = ? WHERE id = ?",
                (status, updated_at, batch_id),
            )
        batch = self.get_batch(batch_id)
        if batch is None:
            raise ValueError(f"Upload batch not found: {batch_id}")
        return batch

    def refresh_batch_status(self, batch_id: str, sample_statuses: dict[str, str]) -> dict[str, Any]:
        batch = self.get_batch(batch_id)
        if batch is None:
            raise ValueError(f"Upload batch not found: {batch_id}")
        statuses = [sample_statuses.get(sid, "unknown") for sid in batch["sampleIds"]]
        if not statuses:
            status = "uploading"
        elif all(s == "analyzed" for s in statuses):
            status = "complete"
        elif any(s in {"analyzing", "queued", "importing", "uploaded"} for s in statuses):
            status = "uploading"
        elif any(s == "analyzed" for s in statuses) and any(s == "failed" for s in statuses):
            status = "partial_failed"
        elif all(s == "failed" for s in statuses):
            status = "partial_failed"
        else:
            status = "uploading"
        return self.update_batch_status(batch_id, status=status)

    @staticmethod
    def _row_to_batch(row: Any) -> dict[str, Any]:
        sample_ids = json.loads(row["sample_ids_json"] or "[]")
        return {
            "id": row["id"],
            "projectId": row["project_id"],
            "status": row["status"],
            "sampleIds": sample_ids if isinstance(sample_ids, list) else [],
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
        }
