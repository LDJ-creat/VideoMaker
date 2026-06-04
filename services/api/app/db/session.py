from __future__ import annotations

import sqlite3
from pathlib import Path


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection


def _migrate_schema(connection: sqlite3.Connection) -> None:
    project_columns = {row[1] for row in connection.execute("PRAGMA table_info(projects)").fetchall()}
    if "cookies_uri" not in project_columns:
        connection.execute("ALTER TABLE projects ADD COLUMN cookies_uri TEXT")

    generation_columns = {
        row[1] for row in connection.execute("PRAGMA table_info(generations)").fetchall()
    }
    if "variant" not in generation_columns:
        connection.execute("ALTER TABLE generations ADD COLUMN variant TEXT")

    tables = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    if "knowledge_entries" not in tables:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS knowledge_entries (
              id TEXT PRIMARY KEY,
              status TEXT NOT NULL,
              title TEXT NOT NULL,
              category TEXT NOT NULL,
              category_slug TEXT NOT NULL,
              style TEXT NOT NULL,
              hook_type TEXT,
              tempo TEXT,
              duration_bucket TEXT,
              slot_pattern TEXT NOT NULL,
              summary TEXT NOT NULL,
              skill_md_uri TEXT NOT NULL,
              structure_json_uri TEXT NOT NULL,
              source_project_id TEXT,
              source_sample_id TEXT,
              version INTEGER NOT NULL DEFAULT 1,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_knowledge_category ON knowledge_entries(category, status);
            CREATE INDEX IF NOT EXISTS idx_knowledge_slot_pattern ON knowledge_entries(slot_pattern);
            """
        )
    if "project_knowledge_selection" not in tables:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS project_knowledge_selection (
              project_id TEXT PRIMARY KEY,
              primary_entry_id TEXT,
              reference_entry_ids_json TEXT NOT NULL DEFAULT '[]',
              mode TEXT NOT NULL DEFAULT 'auto',
              applied_as_structure INTEGER NOT NULL DEFAULT 0,
              recommendation_json TEXT,
              updated_at TEXT NOT NULL,
              FOREIGN KEY (project_id) REFERENCES projects(id)
            )
            """
        )

    sample_columns = {
        row[1] for row in connection.execute("PRAGMA table_info(samples)").fetchall()
    }
    if "upload_batch_id" not in sample_columns:
        connection.execute("ALTER TABLE samples ADD COLUMN upload_batch_id TEXT")

    if "generation_run_id" not in generation_columns:
        connection.execute("ALTER TABLE generations ADD COLUMN generation_run_id TEXT")

    sample_columns_after = {
        row[1] for row in connection.execute("PRAGMA table_info(samples)").fetchall()
    }
    if "upload_batch_id" in sample_columns_after:
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_samples_upload_batch ON samples(upload_batch_id)"
        )

    if "upload_batches" not in tables:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS upload_batches (
              id TEXT PRIMARY KEY,
              project_id TEXT NOT NULL,
              status TEXT NOT NULL,
              sample_ids_json TEXT NOT NULL DEFAULT '[]',
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY (project_id) REFERENCES projects(id)
            );
            CREATE INDEX IF NOT EXISTS idx_upload_batches_project ON upload_batches(project_id, created_at DESC);
            """
        )

    if "project_sample_selection" not in tables:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS project_sample_selection (
              project_id TEXT PRIMARY KEY,
              primary_sample_id TEXT,
              reference_sample_ids_json TEXT NOT NULL DEFAULT '[]',
              active_upload_batch_id TEXT,
              mode TEXT NOT NULL DEFAULT 'auto',
              recommendation_json TEXT,
              updated_at TEXT NOT NULL,
              FOREIGN KEY (project_id) REFERENCES projects(id)
            )
            """
        )

    if "generation_runs" not in tables:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS generation_runs (
              id TEXT PRIMARY KEY,
              project_id TEXT NOT NULL,
              sample_selection_json TEXT NOT NULL,
              synthesized_structure_id TEXT,
              provenance_id TEXT,
              variant_ids_json TEXT NOT NULL DEFAULT '[]',
              generation_ids_json TEXT NOT NULL DEFAULT '[]',
              status TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY (project_id) REFERENCES projects(id)
            );
            CREATE INDEX IF NOT EXISTS idx_generation_runs_project ON generation_runs(project_id, created_at DESC);
            """
        )


def initialize_database(database: Database, *, storage_root: Path | None = None) -> None:
    schema_path = Path(__file__).with_name("schema.sql")
    with database.connect() as connection:
        connection.executescript(schema_path.read_text(encoding="utf-8"))
        _migrate_schema(connection)
    if storage_root is not None:
        from model_gateway.store import ModelGatewayStore

        ModelGatewayStore(database.path, storage_root).ensure_initialized()
