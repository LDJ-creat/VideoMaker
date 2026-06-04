from __future__ import annotations

import json
import uuid
from typing import Any

from app.db.session import Database
from app.services.task_events import now_iso


class GenerationRunStore:
    def __init__(self, database: Database) -> None:
        self.database = database

    def create_run(
        self,
        *,
        project_id: str,
        sample_selection_snapshot: dict[str, Any],
        variant_ids: list[str],
    ) -> dict[str, Any]:
        run_id = str(uuid.uuid4())
        created_at = now_iso()
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO generation_runs (
                  id, project_id, sample_selection_json, synthesized_structure_id,
                  provenance_id, variant_ids_json, generation_ids_json, status,
                  created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    project_id,
                    json.dumps(sample_selection_snapshot, ensure_ascii=False),
                    None,
                    None,
                    json.dumps(variant_ids, separators=(",", ":")),
                    "[]",
                    "running",
                    created_at,
                    created_at,
                ),
            )
        return {
            "id": run_id,
            "projectId": project_id,
            "sampleSelectionSnapshot": sample_selection_snapshot,
            "synthesizedStructureId": None,
            "provenanceId": None,
            "variantIds": variant_ids,
            "generationIds": [],
            "status": "running",
            "createdAt": created_at,
            "updatedAt": created_at,
        }

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT id, project_id, sample_selection_json, synthesized_structure_id,
                       provenance_id, variant_ids_json, generation_ids_json, status,
                       created_at, updated_at
                FROM generation_runs WHERE id = ?
                """,
                (run_id,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_run(row)

    def list_runs(self, project_id: str, *, limit: int = 20) -> list[dict[str, Any]]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT id, project_id, sample_selection_json, synthesized_structure_id,
                       provenance_id, variant_ids_json, generation_ids_json, status,
                       created_at, updated_at
                FROM generation_runs
                WHERE project_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (project_id, limit),
            ).fetchall()
        return [self._row_to_run(row) for row in rows]

    def append_generation(self, run_id: str, generation_id: str) -> dict[str, Any]:
        run = self.get_run(run_id)
        if run is None:
            raise ValueError(f"Generation run not found: {run_id}")
        generation_ids = list(run["generationIds"])
        generation_ids.append(generation_id)
        updated_at = now_iso()
        with self.database.connect() as connection:
            connection.execute(
                """
                UPDATE generation_runs
                SET generation_ids_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (json.dumps(generation_ids, separators=(",", ":")), updated_at, run_id),
            )
        run["generationIds"] = generation_ids
        run["updatedAt"] = updated_at
        return run

    def update_run(
        self,
        run_id: str,
        *,
        status: str | None = None,
        synthesized_structure_id: str | None = None,
        provenance_id: str | None = None,
    ) -> dict[str, Any]:
        fields: list[str] = []
        values: list[Any] = []
        if status is not None:
            fields.append("status = ?")
            values.append(status)
        if synthesized_structure_id is not None:
            fields.append("synthesized_structure_id = ?")
            values.append(synthesized_structure_id)
        if provenance_id is not None:
            fields.append("provenance_id = ?")
            values.append(provenance_id)
        fields.append("updated_at = ?")
        values.append(now_iso())
        values.append(run_id)
        with self.database.connect() as connection:
            connection.execute(
                f"UPDATE generation_runs SET {', '.join(fields)} WHERE id = ?",
                values,
            )
        run = self.get_run(run_id)
        if run is None:
            raise ValueError(f"Generation run not found: {run_id}")
        return run

    @staticmethod
    def _row_to_run(row: Any) -> dict[str, Any]:
        selection = json.loads(row["sample_selection_json"] or "{}")
        variant_ids = json.loads(row["variant_ids_json"] or "[]")
        generation_ids = json.loads(row["generation_ids_json"] or "[]")
        return {
            "id": row["id"],
            "projectId": row["project_id"],
            "sampleSelectionSnapshot": selection,
            "synthesizedStructureId": row["synthesized_structure_id"],
            "provenanceId": row["provenance_id"],
            "variantIds": variant_ids if isinstance(variant_ids, list) else [],
            "generationIds": generation_ids if isinstance(generation_ids, list) else [],
            "status": row["status"],
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
        }
