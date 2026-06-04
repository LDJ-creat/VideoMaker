from __future__ import annotations

import json
from typing import Any

from app.db.session import Database
from app.services.task_events import now_iso


class SampleSelectionStore:
    def __init__(self, database: Database) -> None:
        self.database = database

    def get_selection(self, project_id: str) -> dict[str, Any] | None:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT project_id, primary_sample_id, reference_sample_ids_json,
                       active_upload_batch_id, mode, recommendation_json, updated_at
                FROM project_sample_selection
                WHERE project_id = ?
                """,
                (project_id,),
            ).fetchone()
        if row is None:
            return None
        refs = json.loads(row["reference_sample_ids_json"] or "[]")
        recommendation = (
            json.loads(row["recommendation_json"]) if row["recommendation_json"] else None
        )
        return {
            "projectId": row["project_id"],
            "primarySampleId": row["primary_sample_id"],
            "referenceSampleIds": refs if isinstance(refs, list) else [],
            "activeUploadBatchId": row["active_upload_batch_id"],
            "mode": row["mode"],
            "recommendationSnapshot": recommendation,
            "updatedAt": row["updated_at"],
        }

    def save_selection(self, selection: dict[str, Any]) -> dict[str, Any]:
        updated_at = now_iso()
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO project_sample_selection (
                  project_id, primary_sample_id, reference_sample_ids_json,
                  active_upload_batch_id, mode, recommendation_json, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(project_id) DO UPDATE SET
                  primary_sample_id = excluded.primary_sample_id,
                  reference_sample_ids_json = excluded.reference_sample_ids_json,
                  active_upload_batch_id = excluded.active_upload_batch_id,
                  mode = excluded.mode,
                  recommendation_json = excluded.recommendation_json,
                  updated_at = excluded.updated_at
                """,
                (
                    selection["projectId"],
                    selection.get("primarySampleId"),
                    json.dumps(selection.get("referenceSampleIds") or [], ensure_ascii=False),
                    selection.get("activeUploadBatchId"),
                    selection.get("mode", "auto"),
                    json.dumps(selection.get("recommendationSnapshot"), ensure_ascii=False)
                    if selection.get("recommendationSnapshot")
                    else None,
                    updated_at,
                ),
            )
        selection["updatedAt"] = updated_at
        return selection
