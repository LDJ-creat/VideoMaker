from __future__ import annotations

import json
import shutil
import uuid
from pathlib import Path
from typing import Any

from app.db.session import Database
from app.services.task_events import now_iso
from app.services.variant_registry import default_variant_ids


class ProjectStore:
    def __init__(self, database: Database) -> None:
        self.database = database

    def create_project(self, name: str | None) -> dict[str, Any]:
        project_id = str(uuid.uuid4())
        created_at = now_iso()
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO projects (id, name, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (project_id, name, created_at, created_at),
            )
        return {
            "id": project_id,
            "name": name or "Untitled project",
            "createdAt": created_at,
        }

    def list_projects(self) -> list[dict[str, Any]]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT id, name, created_at FROM projects
                ORDER BY created_at DESC
                """
            ).fetchall()
        return [
            {
                "id": row["id"],
                "name": row["name"] or "Untitled project",
                "createdAt": row["created_at"],
            }
            for row in rows
        ]

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT id, name, created_at FROM projects WHERE id = ?",
                (project_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "id": row["id"],
            "name": row["name"] or "Untitled project",
            "createdAt": row["created_at"],
        }

    def delete_project(self, project_id: str, *, storage_root: Path) -> bool:
        if self.get_project(project_id) is None:
            return False

        with self.database.connect() as connection:
            task_rows = connection.execute(
                "SELECT id FROM tasks WHERE project_id = ?",
                (project_id,),
            ).fetchall()
            task_ids = [str(row["id"]) for row in task_rows]
            if task_ids:
                placeholders = ",".join("?" * len(task_ids))
                connection.execute(
                    f"DELETE FROM task_events WHERE task_id IN ({placeholders})",
                    task_ids,
                )

            connection.execute("DELETE FROM artifacts WHERE project_id = ?", (project_id,))
            connection.execute("DELETE FROM tasks WHERE project_id = ?", (project_id,))
            connection.execute("DELETE FROM samples WHERE project_id = ?", (project_id,))
            connection.execute(
                "DELETE FROM project_assets WHERE project_id = ?",
                (project_id,),
            )
            connection.execute(
                "DELETE FROM project_briefs WHERE project_id = ?",
                (project_id,),
            )
            connection.execute(
                "DELETE FROM generations WHERE project_id = ?",
                (project_id,),
            )
            connection.execute(
                "DELETE FROM project_knowledge_selection WHERE project_id = ?",
                (project_id,),
            )
            connection.execute(
                "DELETE FROM upload_batches WHERE project_id = ?",
                (project_id,),
            )
            connection.execute(
                "DELETE FROM project_sample_selection WHERE project_id = ?",
                (project_id,),
            )
            connection.execute(
                "DELETE FROM generation_runs WHERE project_id = ?",
                (project_id,),
            )
            connection.execute("DELETE FROM projects WHERE id = ?", (project_id,))

        project_dir = storage_root / "projects" / project_id
        if project_dir.is_dir():
            shutil.rmtree(project_dir)

        return True

    def create_sample(
        self,
        *,
        project_id: str,
        source_kind: str,
        source_url: str | None = None,
        video_uri: str | None = None,
        status: str = "uploaded",
        task_id: str | None = None,
        upload_batch_id: str | None = None,
    ) -> dict[str, Any]:
        sample_id = str(uuid.uuid4())
        created_at = now_iso()
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO samples (
                  id, project_id, source_kind, source_url, video_uri, status, task_id,
                  structure_json, upload_batch_id, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sample_id,
                    project_id,
                    source_kind,
                    source_url,
                    video_uri,
                    status,
                    task_id,
                    None,
                    upload_batch_id,
                    created_at,
                    created_at,
                ),
            )
        return {
            "id": sample_id,
            "projectId": project_id,
            "sourceKind": source_kind,
            "status": status,
            "taskId": task_id,
            "uploadBatchId": upload_batch_id,
        }

    def get_sample(self, sample_id: str) -> dict[str, Any] | None:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT id, project_id, source_kind, source_url, video_uri, status, task_id,
                       structure_json, upload_batch_id, created_at, updated_at
                FROM samples WHERE id = ?
                """,
                (sample_id,),
            ).fetchone()
        if row is None:
            return None
        return self._parse_sample_row(row)

    def update_sample(
        self,
        sample_id: str,
        *,
        status: str | None = None,
        video_uri: str | None = None,
        task_id: str | None = None,
        structure: dict[str, Any] | None = None,
    ) -> None:
        fields: list[str] = []
        values: list[Any] = []
        if status is not None:
            fields.append("status = ?")
            values.append(status)
        if video_uri is not None:
            fields.append("video_uri = ?")
            values.append(video_uri)
        if task_id is not None:
            fields.append("task_id = ?")
            values.append(task_id)
        if structure is not None:
            fields.append("structure_json = ?")
            values.append(json.dumps(structure, separators=(",", ":")))
        fields.append("updated_at = ?")
        values.append(now_iso())
        values.append(sample_id)
        with self.database.connect() as connection:
            connection.execute(
                f"UPDATE samples SET {', '.join(fields)} WHERE id = ?",
                values,
            )

    def get_sample_by_task_id(self, task_id: str) -> dict[str, Any] | None:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT id, project_id, source_kind, source_url, video_uri, status, task_id,
                       structure_json, upload_batch_id, created_at, updated_at
                FROM samples WHERE task_id = ?
                """,
                (task_id,),
            ).fetchone()
        if row is None:
            return None
        return self._parse_sample_row(row)

    def get_generation_by_task_id(self, task_id: str) -> dict[str, Any] | None:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT id, project_id, structure_id, inventory_id, gap_report_json, plan_json,
                       status, task_id, variant, generation_run_id
                FROM generations WHERE task_id = ?
                """,
                (task_id,),
            ).fetchone()
        if row is None:
            return None
        return self._parse_generation_row(row)

    def clear_sample_analysis(self, sample_id: str, *, storage_root: Path) -> None:
        sample = self.get_sample(sample_id)
        if sample is None:
            return
        analysis_dir = (
            storage_root
            / "projects"
            / sample["projectId"]
            / "samples"
            / sample_id
            / "analysis"
        )
        if analysis_dir.is_dir():
            shutil.rmtree(analysis_dir)

    def list_samples(self, project_id: str) -> list[dict[str, Any]]:
        return self.list_samples_with_meta(project_id)

    def list_samples_with_meta(self, project_id: str) -> list[dict[str, Any]]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT id, project_id, source_kind, source_url, video_uri, status, task_id,
                       structure_json, upload_batch_id, created_at, updated_at
                FROM samples
                WHERE project_id = ?
                ORDER BY updated_at DESC
                """,
                (project_id,),
            ).fetchall()
        return [self._parse_sample_row(row) for row in rows]

    @staticmethod
    def _parse_sample_row(row: Any) -> dict[str, Any]:
        structure = json.loads(row["structure_json"]) if row["structure_json"] else None
        return {
            "id": row["id"],
            "projectId": row["project_id"],
            "sourceKind": row["source_kind"],
            "sourceUrl": row["source_url"],
            "videoUri": row["video_uri"],
            "status": row["status"],
            "taskId": row["task_id"],
            "structure": structure,
            "uploadBatchId": row["upload_batch_id"],
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
        }

    def get_latest_sample_with_video(self, project_id: str) -> dict[str, Any] | None:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT id, project_id, source_kind, source_url, video_uri, status, task_id,
                       structure_json, upload_batch_id, created_at, updated_at
                FROM samples
                WHERE project_id = ? AND video_uri IS NOT NULL AND video_uri != ''
                ORDER BY updated_at DESC LIMIT 1
                """,
                (project_id,),
            ).fetchone()
        if row is None:
            return None
        return self._parse_sample_row(row)

    def get_latest_analyzed_sample(self, project_id: str) -> dict[str, Any] | None:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT id, project_id, source_kind, source_url, video_uri, status, task_id,
                       structure_json, upload_batch_id, created_at, updated_at
                FROM samples
                WHERE project_id = ?
                  AND structure_json IS NOT NULL
                  AND source_kind != 'knowledge'
                ORDER BY updated_at DESC LIMIT 1
                """,
                (project_id,),
            ).fetchone()
        if row is None:
            return None
        return self._parse_sample_row(row)

    def get_sample_structure(self, sample_id: str) -> dict[str, Any] | None:
        sample = self.get_sample(sample_id)
        if sample is None:
            return None
        return sample.get("structure")

    def get_latest_analyzed_sample_structure(self, project_id: str) -> dict[str, Any] | None:
        """Return structure from a real (non-knowledge) analyzed sample only."""
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT structure_json FROM samples
                WHERE project_id = ?
                  AND structure_json IS NOT NULL
                  AND source_kind != 'knowledge'
                ORDER BY updated_at DESC LIMIT 1
                """,
                (project_id,),
            ).fetchone()
        if row is None or not row["structure_json"]:
            return None
        return json.loads(row["structure_json"])

    def get_latest_sample_structure(self, project_id: str) -> dict[str, Any] | None:
        """Prefer real analyzed samples; fall back to knowledge-applied structure."""
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT structure_json FROM samples
                WHERE project_id = ? AND structure_json IS NOT NULL
                ORDER BY CASE WHEN source_kind = 'knowledge' THEN 1 ELSE 0 END,
                         updated_at DESC
                LIMIT 1
                """,
                (project_id,),
            ).fetchone()
        if row is None or not row["structure_json"]:
            return None
        return json.loads(row["structure_json"])

    def add_asset(
        self,
        *,
        project_id: str,
        asset_type: str,
        uri: str,
        description: str | None = None,
        tags: list[str] | None = None,
        duration_sec: float | None = None,
    ) -> dict[str, Any]:
        asset_id = str(uuid.uuid4())
        created_at = now_iso()
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO project_assets (
                  id, project_id, type, uri, description, tags_json, duration_sec, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    asset_id,
                    project_id,
                    asset_type,
                    uri,
                    description,
                    json.dumps(tags or [], separators=(",", ":")),
                    duration_sec,
                    created_at,
                ),
            )
        return {"id": asset_id, "type": asset_type, "uri": uri}

    def get_asset(self, asset_id: str) -> dict[str, Any] | None:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT id, project_id, type, uri, description, tags_json, duration_sec
                FROM project_assets WHERE id = ?
                """,
                (asset_id,),
            ).fetchone()
        if row is None:
            return None
        asset: dict[str, Any] = {
            "id": row["id"],
            "projectId": row["project_id"],
            "type": row["type"],
            "uri": row["uri"],
        }
        if row["description"]:
            asset["description"] = row["description"]
        tags = json.loads(row["tags_json"] or "[]")
        if tags:
            asset["tags"] = tags
        if row["duration_sec"] is not None:
            asset["durationSec"] = row["duration_sec"]
        return asset

    def list_assets(self, project_id: str) -> list[dict[str, Any]]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT id, type, uri, description, tags_json, duration_sec
                FROM project_assets WHERE project_id = ? ORDER BY created_at ASC
                """,
                (project_id,),
            ).fetchall()
        assets: list[dict[str, Any]] = []
        for row in rows:
            asset: dict[str, Any] = {
                "id": row["id"],
                "type": row["type"],
                "uri": row["uri"],
            }
            if row["description"]:
                asset["description"] = row["description"]
            tags = json.loads(row["tags_json"] or "[]")
            if tags:
                asset["tags"] = tags
            if row["duration_sec"] is not None:
                asset["durationSec"] = row["duration_sec"]
            assets.append(asset)
        return assets

    def save_brief(self, project_id: str, brief: dict[str, Any]) -> None:
        updated_at = now_iso()
        payload = json.dumps(brief, separators=(",", ":"))
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO project_briefs (project_id, brief_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(project_id) DO UPDATE SET brief_json = excluded.brief_json, updated_at = excluded.updated_at
                """,
                (project_id, payload, updated_at),
            )

    def get_brief(self, project_id: str) -> dict[str, Any] | None:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT brief_json FROM project_briefs WHERE project_id = ?",
                (project_id,),
            ).fetchone()
        if row is None:
            return None
        return json.loads(row["brief_json"])

    def create_generation(
        self,
        *,
        project_id: str,
        task_id: str | None = None,
        status: str = "queued",
        variant: str | None = None,
        generation_run_id: str | None = None,
    ) -> dict[str, Any]:
        generation_id = str(uuid.uuid4())
        created_at = now_iso()
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO generations (
                  id, project_id, structure_id, inventory_id, gap_report_json, plan_json,
                  status, task_id, variant, generation_run_id, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    generation_id,
                    project_id,
                    None,
                    None,
                    None,
                    None,
                    status,
                    task_id,
                    variant,
                    generation_run_id,
                    created_at,
                    created_at,
                ),
            )
        return {
            "id": generation_id,
            "projectId": project_id,
            "status": status,
            "taskId": task_id,
            "variant": variant,
            "generationRunId": generation_run_id,
        }

    def update_generation(
        self,
        generation_id: str,
        *,
        status: str | None = None,
        structure_id: str | None = None,
        inventory_id: str | None = None,
        gap_report: dict[str, Any] | None = None,
        plan: dict[str, Any] | None = None,
        task_id: str | None = None,
    ) -> None:
        fields: list[str] = []
        values: list[Any] = []
        if status is not None:
            fields.append("status = ?")
            values.append(status)
        if structure_id is not None:
            fields.append("structure_id = ?")
            values.append(structure_id)
        if inventory_id is not None:
            fields.append("inventory_id = ?")
            values.append(inventory_id)
        if gap_report is not None:
            fields.append("gap_report_json = ?")
            values.append(json.dumps(gap_report, separators=(",", ":")))
        if plan is not None:
            fields.append("plan_json = ?")
            values.append(json.dumps(plan, separators=(",", ":")))
        if task_id is not None:
            fields.append("task_id = ?")
            values.append(task_id)
        fields.append("updated_at = ?")
        values.append(now_iso())
        values.append(generation_id)
        with self.database.connect() as connection:
            connection.execute(
                f"UPDATE generations SET {', '.join(fields)} WHERE id = ?",
                values,
            )

    def _parse_generation_row(self, row: Any) -> dict[str, Any]:
        plan = json.loads(row["plan_json"]) if row["plan_json"] else None
        gap_report = json.loads(row["gap_report_json"]) if row["gap_report_json"] else None
        variant = row["variant"]
        if variant is None and isinstance(plan, dict):
            variant = plan.get("variant")
        return {
            "id": row["id"],
            "projectId": row["project_id"],
            "structureId": row["structure_id"],
            "inventoryId": row["inventory_id"],
            "gapReport": gap_report,
            "plan": plan,
            "status": row["status"],
            "taskId": row["task_id"],
            "variant": variant,
            "generationRunId": row["generation_run_id"]
            if "generation_run_id" in row.keys()
            else None,
        }

    def get_generation(self, generation_id: str) -> dict[str, Any] | None:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT id, project_id, structure_id, inventory_id, gap_report_json, plan_json,
                       status, task_id, variant, generation_run_id
                FROM generations WHERE id = ?
                """,
                (generation_id,),
            ).fetchone()
        if row is None:
            return None
        return self._parse_generation_row(row)

    def list_generations_for_project(self, project_id: str) -> list[dict[str, Any]]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT id, project_id, structure_id, inventory_id, gap_report_json, plan_json,
                       status, task_id, variant, generation_run_id, created_at, updated_at
                FROM generations
                WHERE project_id = ?
                ORDER BY COALESCE(updated_at, created_at) DESC, created_at DESC
                """,
                (project_id,),
            ).fetchall()
        return [self._parse_generation_row(row) for row in rows]

    def list_generations_for_run(self, generation_run_id: str) -> list[dict[str, Any]]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT id, project_id, structure_id, inventory_id, gap_report_json, plan_json,
                       status, task_id, variant, generation_run_id
                FROM generations
                WHERE generation_run_id = ?
                ORDER BY created_at ASC
                """,
                (generation_run_id,),
            ).fetchall()
        return [self._parse_generation_row(row) for row in rows]

    def get_latest_generation_with_plan(self, project_id: str) -> dict[str, Any] | None:
        records = self.get_latest_generations_with_plan(project_id)
        return records[0] if records else None

    def get_latest_generations_with_plan(self, project_id: str) -> list[dict[str, Any]]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT id, project_id, structure_id, inventory_id, gap_report_json, plan_json,
                       status, task_id, variant, generation_run_id
                FROM generations
                WHERE project_id = ?
                  AND (
                    plan_json IS NOT NULL
                    OR (
                      task_id IS NOT NULL
                      AND status IN ('failed', 'running', 'pending', 'cancelled')
                    )
                  )
                ORDER BY updated_at DESC
                """,
                (project_id,),
            ).fetchall()
        latest_by_variant: dict[str, dict[str, Any]] = {}
        for row in rows:
            record = self._parse_generation_row(row)
            variant = str(record.get("variant") or "default")
            if variant in latest_by_variant:
                continue
            latest_by_variant[variant] = record
        order = default_variant_ids()
        ordered: list[dict[str, Any]] = []
        for variant_id in order:
            if variant_id in latest_by_variant:
                ordered.append(latest_by_variant[variant_id])
        for variant_id, record in latest_by_variant.items():
            if variant_id not in order:
                ordered.append(record)
        return ordered
