from __future__ import annotations

import json
import uuid
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from knowledge.paths import category_slug as compute_category_slug

from app.main import create_app
from app.services.project_store import ProjectStore

def _client(tmp_path: Path) -> TestClient:
    db_path = tmp_path / "test.sqlite3"
    storage_root = tmp_path / "storage"
    storage_root.mkdir(parents=True, exist_ok=True)
    return TestClient(
        create_app(database_path=db_path, storage_root=storage_root, sync_pipelines=True)
    )


def _structure(project_id: str, sample_id: str) -> dict:
    return {
        "id": "video-structure-old",
        "projectId": project_id,
        "sourceVideoId": sample_id,
        "version": "p1-v3",
        "metadata": {"durationSec": 12.0},
        "narrative": {"summary": "test", "segments": []},
        "slots": [],
        "analysisQuality": {"warnings": [], "locale": "zh", "promoteReady": True},
    }


def _seed_importable_entry(
    client: TestClient,
    tmp_path: Path,
    *,
    slug: str = "ecommerce",
    category: str = "电商带货",
    title: str = "电商促销",
    marker: str = "a",
) -> tuple[str, str, str]:
    project_id = client.post("/api/projects", json={"name": "Source"}).json()["id"]
    store = ProjectStore(client.app.state.db)
    sample = store.create_sample(project_id=project_id, source_kind="local", status="uploaded")
    sample_id = sample["id"]
    video_path = (
        tmp_path
        / "storage"
        / "projects"
        / project_id
        / "samples"
        / sample_id
        / "source.mp4"
    )
    video_path.parent.mkdir(parents=True, exist_ok=True)
    video_path.write_bytes(b"fake-video")
    store.update_sample(sample_id, video_uri=str(video_path.resolve()))

    entry_id = str(uuid.uuid4())
    knowledge_dir = tmp_path / "storage" / "knowledge" / slug / entry_id
    knowledge_dir.mkdir(parents=True, exist_ok=True)
    (knowledge_dir / "video-structure.json").write_text(
        json.dumps(_structure(project_id, sample_id)),
        encoding="utf-8",
    )
    (knowledge_dir / "structure-skill.md").write_text("## 适用场景\n\n测试\n", encoding="utf-8")
    created_at = "2026-06-09T00:00:00Z"
    with client.app.state.db.connect() as connection:
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
                title,
                category,
                slug,
                "快节奏",
                "pain_point",
                "fast",
                "30s",
                f"hook→cta-{marker}",
                f"摘要 {marker}",
                f"knowledge/{slug}/{entry_id}/structure-skill.md",
                f"knowledge/{slug}/{entry_id}/video-structure.json",
                project_id,
                sample_id,
                1,
                "structure",
                created_at,
                created_at,
            ),
        )
    return entry_id, project_id, sample_id


def _seed_non_importable_entry(
    client: TestClient,
    tmp_path: Path,
    *,
    slug: str = "ecommerce",
    category: str = "电商带货",
    title: str = "不可导入",
) -> str:
    entry_id, project_id, sample_id = _seed_importable_entry(
        client,
        tmp_path,
        slug=slug,
        category=category,
        title=title,
        marker="blocked",
    )
    video_path = (
        tmp_path
        / "storage"
        / "projects"
        / project_id
        / "samples"
        / sample_id
        / "source.mp4"
    )
    if video_path.exists():
        video_path.unlink()
    return entry_id


def test_list_knowledge_categories_empty(tmp_path: Path) -> None:
    client = _client(tmp_path)
    response = client.get("/api/knowledge/categories")
    assert response.status_code == 200
    assert response.json()["categories"] == []


def test_list_and_get_knowledge_category(tmp_path: Path) -> None:
    client = _client(tmp_path)
    entry_id, _, _ = _seed_importable_entry(client, tmp_path, marker="1")
    _seed_importable_entry(
        client,
        tmp_path,
        title="电商促销 B",
        marker="2",
    )

    listed = client.get("/api/knowledge/categories")
    assert listed.status_code == 200
    categories = listed.json()["categories"]
    assert len(categories) == 1
    assert categories[0]["categorySlug"] == "ecommerce"
    assert categories[0]["entryCount"] == 2

    detail = client.get("/api/knowledge/categories/ecommerce")
    assert detail.status_code == 200
    body = detail.json()
    assert body["category"] == "电商带货"
    assert len(body["entries"]) == 2
    assert all(item["importable"] for item in body["entries"])
    assert any(item["entryId"] == entry_id for item in body["entries"])


def test_create_project_from_knowledge_template(tmp_path: Path) -> None:
    client = _client(tmp_path)
    primary_id, _, _ = _seed_importable_entry(client, tmp_path, marker="primary")
    ref_id, _, _ = _seed_importable_entry(client, tmp_path, title="参考 B", marker="ref")

    response = client.post(
        "/api/projects/from-knowledge-template",
        json={
            "name": "模板项目",
            "categorySlug": "ecommerce",
            "primaryEntryId": primary_id,
            "referenceEntryIds": [ref_id],
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["project"]["name"] == "模板项目"
    assert len(body["importedSamples"]) == 2
    assert body["sampleSelection"]["primarySampleId"] == body["importedSamples"][0]["sampleId"]
    assert body["knowledgeSelection"]["primaryEntryId"] == primary_id
    assert body["knowledgeSelection"]["mode"] == "user_override"
    assert body["knowledgeSelection"]["appliedAsStructure"] is False

    samples = client.get(f"/api/projects/{body['project']['id']}/samples")
    assert samples.status_code == 200
    assert len(samples.json()["samples"]) == 2


def test_create_project_rejects_three_references(tmp_path: Path) -> None:
    client = _client(tmp_path)
    primary_id, _, _ = _seed_importable_entry(client, tmp_path, marker="1")
    ref_a, _, _ = _seed_importable_entry(client, tmp_path, title="B", marker="2")
    ref_b, _, _ = _seed_importable_entry(client, tmp_path, title="C", marker="3")
    ref_c, _, _ = _seed_importable_entry(client, tmp_path, title="D", marker="4")

    response = client.post(
        "/api/projects/from-knowledge-template",
        json={
            "name": "Too many refs",
            "categorySlug": "ecommerce",
            "primaryEntryId": primary_id,
            "referenceEntryIds": [ref_a, ref_b, ref_c],
        },
    )
    assert response.status_code == 422


def test_get_knowledge_category_not_found(tmp_path: Path) -> None:
    client = _client(tmp_path)
    response = client.get("/api/knowledge/categories/missing-slug")
    assert response.status_code == 404


def test_chinese_category_uses_cat_hash_slug(tmp_path: Path) -> None:
    client = _client(tmp_path)
    category = "美妆护肤"
    slug = compute_category_slug(category)
    assert slug.startswith("cat-")

    _seed_importable_entry(
        client,
        tmp_path,
        slug=slug,
        category=category,
        title="护肤种草",
        marker="cn",
    )

    listed = client.get("/api/knowledge/categories")
    assert listed.status_code == 200
    categories = listed.json()["categories"]
    assert len(categories) == 1
    assert categories[0]["categorySlug"] == slug
    assert categories[0]["category"] == category

    detail = client.get(f"/api/knowledge/categories/{slug}")
    assert detail.status_code == 200
    assert detail.json()["category"] == category


def test_category_detail_marks_non_importable_entry(tmp_path: Path) -> None:
    client = _client(tmp_path)
    blocked_id = _seed_non_importable_entry(client, tmp_path)

    detail = client.get("/api/knowledge/categories/ecommerce")
    assert detail.status_code == 200
    blocked = next(item for item in detail.json()["entries"] if item["entryId"] == blocked_id)
    assert blocked["importable"] is False
    assert blocked["importBlockReason"]


def test_create_project_rejects_primary_as_reference(tmp_path: Path) -> None:
    client = _client(tmp_path)
    primary_id, _, _ = _seed_importable_entry(client, tmp_path, marker="primary")

    response = client.post(
        "/api/projects/from-knowledge-template",
        json={
            "name": "Bad selection",
            "categorySlug": "ecommerce",
            "primaryEntryId": primary_id,
            "referenceEntryIds": [primary_id],
        },
    )
    assert response.status_code == 422


def test_create_project_rejects_duplicate_references(tmp_path: Path) -> None:
    client = _client(tmp_path)
    primary_id, _, _ = _seed_importable_entry(client, tmp_path, marker="primary")
    ref_id, _, _ = _seed_importable_entry(client, tmp_path, title="参考 B", marker="ref")

    response = client.post(
        "/api/projects/from-knowledge-template",
        json={
            "name": "Duplicate refs",
            "categorySlug": "ecommerce",
            "primaryEntryId": primary_id,
            "referenceEntryIds": [ref_id, ref_id],
        },
    )
    assert response.status_code == 422


def test_create_project_rejects_non_importable_entry(tmp_path: Path) -> None:
    client = _client(tmp_path)
    blocked_id = _seed_non_importable_entry(client, tmp_path)
    primary_id, _, _ = _seed_importable_entry(client, tmp_path, marker="primary")

    response = client.post(
        "/api/projects/from-knowledge-template",
        json={
            "name": "Blocked import",
            "categorySlug": "ecommerce",
            "primaryEntryId": primary_id,
            "referenceEntryIds": [blocked_id],
        },
    )
    assert response.status_code == 422


def test_create_project_rolls_back_when_import_fails(tmp_path: Path) -> None:
    client = _client(tmp_path)
    primary_id, _, _ = _seed_importable_entry(client, tmp_path, marker="primary")
    ref_id, _, _ = _seed_importable_entry(client, tmp_path, title="参考 B", marker="ref")
    projects_before = client.get("/api/projects").json()["projects"]

    with patch(
        "app.services.knowledge_template_bootstrap.import_sample_from_knowledge_entry",
        side_effect=ValueError("simulated import failure"),
    ):
        response = client.post(
            "/api/projects/from-knowledge-template",
            json={
                "name": "Rollback me",
                "categorySlug": "ecommerce",
                "primaryEntryId": primary_id,
                "referenceEntryIds": [ref_id],
            },
        )

    assert response.status_code == 422
    projects_after = client.get("/api/projects").json()["projects"]
    assert len(projects_after) == len(projects_before)
    assert all(project["name"] != "Rollback me" for project in projects_after)
    assert not any(
        (tmp_path / "storage" / "projects" / project["id"]).exists()
        for project in projects_after
        if project["name"] == "Rollback me"
    )
