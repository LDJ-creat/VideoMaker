from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from app.services.knowledge_store import KnowledgeStore
from app.services.project_store import ProjectStore
from app.services.sample_seed_service import import_sample_from_knowledge_entry, rewrite_structure_ids


def _structure(project_id: str, sample_id: str) -> dict:
    return {
        "id": "video-structure-old",
        "projectId": project_id,
        "sourceVideoId": sample_id,
        "version": "p1-v3",
        "metadata": {"durationSec": 12.0},
        "narrative": {"summary": "test", "segments": []},
        "slots": [],
    }


def test_rewrite_structure_ids() -> None:
    result = rewrite_structure_ids(
        _structure("proj-old", "sample-old"),
        project_id="proj-new",
        sample_id="sample-new",
    )
    assert result["projectId"] == "proj-new"
    assert result["sourceVideoId"] == "sample-new"
    assert result["id"] == "video-structure-sample-new"


def test_import_sample_from_knowledge_entry(tmp_path: Path) -> None:
    storage_root = tmp_path / "storage"
    db_path = tmp_path / "test.sqlite3"
    from app.db.session import Database, initialize_database

    database = Database(db_path)
    initialize_database(database, storage_root=storage_root)
    project_store = ProjectStore(database)
    knowledge_store = KnowledgeStore(database, storage_root)

    source_project = project_store.create_project("Source")
    source_project_id = source_project["id"]
    source_sample = project_store.create_sample(
        project_id=source_project_id,
        source_kind="local",
        status="uploaded",
    )
    source_sample_id = source_sample["id"]

    video_path = (
        storage_root
        / "projects"
        / source_project_id
        / "samples"
        / source_sample_id
        / "source.mp4"
    )
    video_path.parent.mkdir(parents=True, exist_ok=True)
    video_path.write_bytes(b"fake-video")
    project_store.update_sample(source_sample_id, video_uri=str(video_path.resolve()))

    analysis_root = video_path.parent / "analysis"
    analysis_root.mkdir(parents=True, exist_ok=True)
    (analysis_root / "sample-analysis.json").write_text("{}", encoding="utf-8")

    entry_id = str(uuid.uuid4())
    slug = "ecommerce"
    knowledge_dir = storage_root / "knowledge" / slug / entry_id
    knowledge_dir.mkdir(parents=True, exist_ok=True)
    structure = _structure(source_project_id, source_sample_id)
    structure_path = knowledge_dir / "video-structure.json"
    structure_path.write_text(json.dumps(structure), encoding="utf-8")
    skill_path = knowledge_dir / "structure-skill.md"
    skill_path.write_text("## 适用场景\n\n测试\n", encoding="utf-8")

    created_at = "2026-06-09T00:00:00Z"
    with database.connect() as connection:
        connection.execute(
            """
            INSERT INTO knowledge_entries (
              id, status, title, category, category_slug, style, hook_type, tempo,
              duration_bucket, slot_pattern, summary, skill_md_uri, structure_json_uri,
              source_project_id, source_sample_id, version, entry_kind, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry_id,
                "published",
                "电商促销",
                "电商带货",
                slug,
                "快节奏",
                "pain_point",
                "fast",
                "30s",
                "hook→cta",
                "测试摘要",
                f"knowledge/{slug}/{entry_id}/structure-skill.md",
                f"knowledge/{slug}/{entry_id}/video-structure.json",
                source_project_id,
                source_sample_id,
                1,
                "structure",
                created_at,
                created_at,
            ),
        )

    entry = knowledge_store.get_entry(entry_id)
    assert entry is not None

    target_project = project_store.create_project("Target")
    target_project_id = target_project["id"]

    new_sample_id = import_sample_from_knowledge_entry(
        storage_root,
        project_store,
        knowledge_store,
        target_project_id=target_project_id,
        entry=entry,
    )

    imported = project_store.get_sample(new_sample_id)
    assert imported is not None
    assert imported["status"] == "analyzed"
    assert imported["structure"] is not None
    assert imported["structure"]["projectId"] == target_project_id
    assert imported["structure"]["sourceVideoId"] == new_sample_id

    copied_video = (
        storage_root / "projects" / target_project_id / "samples" / new_sample_id / "source.mp4"
    )
    assert copied_video.is_file()
    assert (copied_video.parent / "analysis" / "video-structure.json").is_file()
