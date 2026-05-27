from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from app.db.session import Database

TERMINAL_STATUSES = {"succeeded", "failed", "cancelled"}


def now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class TaskEventService:
    def __init__(self, database: Database) -> None:
        self.database = database

    def create_task(self, project_id: str | None, stage: str, message: str) -> dict[str, Any]:
        task_id = str(uuid.uuid4())
        event = {
            "taskId": task_id,
            "status": "queued",
            "stage": stage,
            "progress": 0,
            "message": message,
            "updatedAt": now_iso(),
        }

        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO tasks (id, project_id, status, stage, progress, message, error_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    project_id,
                    event["status"],
                    event["stage"],
                    event["progress"],
                    event["message"],
                    None,
                    event["updatedAt"],
                    event["updatedAt"],
                ),
            )
            self._insert_event(connection, task_id, event)

        return event

    def update_task(
        self,
        task_id: str,
        *,
        status: str,
        stage: str,
        progress: int,
        message: str,
        artifact_refs: list[dict[str, Any]] | None = None,
        error: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        event: dict[str, Any] = {
            "taskId": task_id,
            "status": status,
            "stage": stage,
            "progress": progress,
            "message": message,
            "updatedAt": now_iso(),
        }
        if artifact_refs:
            event["artifactRefs"] = artifact_refs
        if error:
            event["error"] = error

        with self.database.connect() as connection:
            cursor = connection.execute("SELECT id FROM tasks WHERE id = ?", (task_id,))
            if cursor.fetchone() is None:
                raise KeyError(task_id)

            connection.execute(
                """
                UPDATE tasks
                SET status = ?, stage = ?, progress = ?, message = ?, error_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    status,
                    stage,
                    progress,
                    message,
                    json.dumps(error) if error else None,
                    event["updatedAt"],
                    task_id,
                ),
            )
            self._insert_event(connection, task_id, event)

        return event

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT id, status, stage, progress, message, error_json, updated_at FROM tasks WHERE id = ?",
                (task_id,),
            ).fetchone()
            if row is None:
                return None

            artifact_rows = connection.execute(
                "SELECT id, type, uri, created_at FROM artifacts WHERE task_id = ? ORDER BY created_at ASC",
                (task_id,),
            ).fetchall()

        event: dict[str, Any] = {
            "taskId": row["id"],
            "status": row["status"],
            "stage": row["stage"],
            "progress": row["progress"],
            "message": row["message"],
            "updatedAt": row["updated_at"],
        }
        if row["error_json"]:
            event["error"] = json.loads(row["error_json"])
        if artifact_rows:
            event["artifactRefs"] = [
                {
                    "id": artifact["id"],
                    "type": artifact["type"],
                    "uri": artifact["uri"],
                    "createdAt": artifact["created_at"],
                }
                for artifact in artifact_rows
            ]
        return event

    def list_events(self, task_id: str, after_id: int = 0) -> list[dict[str, Any]]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT event_json
                FROM task_events
                WHERE task_id = ? AND id > ?
                ORDER BY id ASC
                """,
                (task_id, after_id),
            ).fetchall()

        return [json.loads(row["event_json"]) for row in rows]

    def is_terminal(self, status: str) -> bool:
        return status in TERMINAL_STATUSES

    def _insert_event(self, connection: Any, task_id: str, event: dict[str, Any]) -> None:
        connection.execute(
            "INSERT INTO task_events (task_id, event_json, created_at) VALUES (?, ?, ?)",
            (task_id, json.dumps(event, separators=(",", ":")), event["updatedAt"]),
        )
