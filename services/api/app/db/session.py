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


def initialize_database(database: Database) -> None:
    schema_path = Path(__file__).with_name("schema.sql")
    with database.connect() as connection:
        connection.executescript(schema_path.read_text(encoding="utf-8"))
        _migrate_schema(connection)
