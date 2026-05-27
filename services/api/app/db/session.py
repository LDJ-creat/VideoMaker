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


def initialize_database(database: Database) -> None:
    schema_path = Path(__file__).with_name("schema.sql")
    with database.connect() as connection:
        connection.executescript(schema_path.read_text(encoding="utf-8"))
