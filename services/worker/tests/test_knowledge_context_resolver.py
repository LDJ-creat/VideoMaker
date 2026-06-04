from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path

from app.knowledge.context_resolver import resolve_knowledge_context


def _init_schema(database_path: Path) -> None:
    connection = sqlite3.connect(database_path)
    try:
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
            CREATE TABLE IF NOT EXISTS project_knowledge_selection (
              project_id TEXT PRIMARY KEY,
              primary_entry_id TEXT,
              reference_entry_ids_json TEXT NOT NULL DEFAULT '[]',
              mode TEXT NOT NULL DEFAULT 'auto',
              applied_as_structure INTEGER NOT NULL DEFAULT 0,
              recommendation_json TEXT,
              updated_at TEXT NOT NULL
            );
            """
        )
        connection.commit()
    finally:
        connection.close()


def _seed_knowledge_db(
    database_path: Path,
    storage_root: Path,
    *,
    project_id: str,
    entry_id: str,
) -> None:
    skill_rel = f"knowledge/ecommerce/{entry_id}/structure-skill.md"
    structure_rel = f"knowledge/ecommerce/{entry_id}/video-structure.json"
    skill_path = storage_root / skill_rel
    skill_path.parent.mkdir(parents=True, exist_ok=True)
    skill_path.write_text(
        "## 适用场景\n\n测试场景\n\n## 槽位模板\n\n| role | 占比 |\n| hook | 10% |\n",
        encoding="utf-8",
    )
    (storage_root / structure_rel).write_text("{}", encoding="utf-8")

    connection = sqlite3.connect(database_path)
    try:
        connection.execute(
            """
            INSERT INTO knowledge_entries (
                id, status, title, category, category_slug, style, hook_type,
                tempo, duration_bucket, slot_pattern, summary,
                skill_md_uri, structure_json_uri, source_project_id, source_sample_id,
                version, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry_id,
                "published",
                "电商促销",
                "电商带货",
                "ecommerce",
                "快节奏",
                "pain_point",
                "fast",
                "30s",
                "hook→cta",
                "测试摘要",
                skill_rel,
                structure_rel,
                None,
                None,
                1,
                "2026-06-03T00:00:00Z",
                "2026-06-03T00:00:00Z",
            ),
        )
        connection.execute(
            """
            INSERT INTO project_knowledge_selection (
                project_id, primary_entry_id, reference_entry_ids_json, mode,
                applied_as_structure, recommendation_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_id,
                entry_id,
                "[]",
                "auto",
                1,
                None,
                "2026-06-03T00:00:00Z",
            ),
        )
        connection.commit()
    finally:
        connection.close()


def test_resolve_knowledge_context_l1_vs_l2(tmp_path: Path) -> None:
    database_path = tmp_path / "test.sqlite3"
    storage_root = tmp_path / "storage"
    project_id = str(uuid.uuid4())
    entry_id = str(uuid.uuid4())

    _init_schema(database_path)
    _seed_knowledge_db(
        database_path,
        storage_root,
        project_id=project_id,
        entry_id=entry_id,
    )

    l1 = resolve_knowledge_context(
        storage_root=storage_root,
        database_path=database_path,
        project_id=project_id,
        level=1,
        weak_slot_count=0,
    )
    assert l1["level"] == 1
    assert l1["primary"] is not None
    assert "测试场景" in l1["primary"]["content"]
    assert "## 适用场景" not in l1["primary"]["content"]

    l2 = resolve_knowledge_context(
        storage_root=storage_root,
        database_path=database_path,
        project_id=project_id,
        level=1,
        weak_slot_count=2,
    )
    assert l2["level"] == 2
    assert l2["primary"] is not None
    assert "## 适用场景" in l2["primary"]["content"]
