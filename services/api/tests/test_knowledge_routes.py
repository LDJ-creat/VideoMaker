from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.db.session import Database
from app.main import create_app
from app.services.project_store import ProjectStore


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    db_path = tmp_path / "test.sqlite3"
    storage_root = tmp_path / "storage"
    storage_root.mkdir(parents=True, exist_ok=True)
    app = create_app(database_path=db_path, storage_root=storage_root, sync_pipelines=True)
    return TestClient(app)


def _create_project(client: TestClient) -> str:
    response = client.post("/api/projects", json={"name": "Knowledge Test"})
    assert response.status_code == 201
    return response.json()["id"]


def _sample_structure(project_id: str, sample_id: str, *, marker: str) -> dict:
    return {
        "id": f"video-structure-{marker}",
        "projectId": project_id,
        "sourceVideoId": sample_id,
        "version": "p0-v1",
        "metadata": {"durationSec": 30.0},
        "narrative": {"summary": marker, "segments": [{"role": "hook"}]},
        "rhythm": {
            "totalDurationSec": 30.0,
            "shotCount": 4,
            "avgShotDurationSec": 7.5,
            "tempo": "fast",
            "beatPoints": [],
            "shotBoundaries": [],
        },
        "packaging": {"visualDensity": "medium"},
        "slots": [],
        "evidence": [],
        "confidence": 0.8,
    }


def _write_draft(
    tmp_path: Path,
    project_id: str,
    sample_id: str,
    *,
    marker: str = "电商促销结构",
) -> None:
    draft_root = (
        tmp_path
        / "storage"
        / "projects"
        / project_id
        / "knowledge"
        / "drafts"
        / sample_id
    )
    draft_root.mkdir(parents=True, exist_ok=True)
    structure = _sample_structure(project_id, sample_id, marker=marker)
    (draft_root / "video-structure.json").write_text(json.dumps(structure), encoding="utf-8")
    (draft_root / "structure-skill.md").write_text("## 适用场景\n\n测试\n", encoding="utf-8")


def _promote_entry(client: TestClient, project_id: str, sample_id: str) -> str:
    promote = client.post(
        f"/api/projects/{project_id}/samples/{sample_id}/knowledge/promote",
        json={
            "title": "电商促销",
            "category": "电商带货",
            "style": "快节奏促销",
            "hookType": "pain_point",
        },
    )
    assert promote.status_code == 200
    return promote.json()["entry"]["id"]


def test_promote_and_apply_knowledge(client: TestClient, tmp_path: Path) -> None:
    project_id = _create_project(client)
    sample_id = str(uuid.uuid4())
    _write_draft(tmp_path, project_id, sample_id)
    entry_id = _promote_entry(client, project_id, sample_id)

    listing = client.get("/api/knowledge/entries")
    assert listing.status_code == 200
    assert any(item["id"] == entry_id for item in listing.json()["entries"])

    client.post(
        f"/api/projects/{project_id}/brief",
        json={"topic": "电商带货", "sellingPoints": ["优惠"], "mustMention": [], "avoidMention": []},
    )
    recommend = client.post(f"/api/projects/{project_id}/knowledge/recommend")
    assert recommend.status_code == 200
    selection = client.get(f"/api/projects/{project_id}/knowledge/selection")
    assert selection.json()["selection"]["primaryEntryId"] == entry_id

    apply = client.post(
        f"/api/projects/{project_id}/structure-from-knowledge",
        json={"entryId": entry_id, "applyStructure": True},
    )
    assert apply.status_code == 200

    samples = client.get(f"/api/projects/{project_id}/samples")
    assert any(item.get("sourceKind") == "knowledge" for item in samples.json()["samples"])


def test_generation_plan_auto_binds_knowledge(client: TestClient, tmp_path: Path) -> None:
    project_id = _create_project(client)
    sample_id = str(uuid.uuid4())
    _write_draft(tmp_path, project_id, sample_id)
    _promote_entry(client, project_id, sample_id)

    client.post(
        f"/api/projects/{project_id}/brief",
        json={"topic": "电商带货", "sellingPoints": ["优惠"], "mustMention": [], "avoidMention": []},
    )

    generation = client.post(f"/api/projects/{project_id}/generation-plan")
    assert generation.status_code == 201, generation.text

    samples = client.get(f"/api/projects/{project_id}/samples")
    assert any(item.get("sourceKind") == "knowledge" for item in samples.json()["samples"])

    selection = client.get(f"/api/projects/{project_id}/knowledge/selection")
    assert selection.status_code == 200
    assert selection.json()["selection"]["primaryEntryId"] is not None


def test_get_latest_sample_structure_prefers_real_sample(
    client: TestClient,
    tmp_path: Path,
) -> None:
    project_id = _create_project(client)
    store = ProjectStore(Database(tmp_path / "test.sqlite3"))

    real = store.create_sample(project_id=project_id, source_kind="local", status="analyzed")
    knowledge = store.create_sample(project_id=project_id, source_kind="knowledge", status="analyzed")

    real_structure = _sample_structure(project_id, real["id"], marker="real-sample")
    knowledge_structure = _sample_structure(project_id, knowledge["id"], marker="knowledge-sample")

    store.update_sample(real["id"], structure=real_structure)
    store.update_sample(knowledge["id"], structure=knowledge_structure)

    selected = store.get_latest_sample_structure(project_id)
    assert selected is not None
    assert selected["narrative"]["summary"] == "real-sample"

    analyzed_only = store.get_latest_analyzed_sample_structure(project_id)
    assert analyzed_only is not None
    assert analyzed_only["narrative"]["summary"] == "real-sample"


def test_apply_structure_blocked_when_real_sample_exists(
    client: TestClient,
    tmp_path: Path,
) -> None:
    project_id = _create_project(client)
    draft_sample_id = str(uuid.uuid4())
    _write_draft(tmp_path, project_id, draft_sample_id)
    entry_id = _promote_entry(client, project_id, draft_sample_id)

    db_path = tmp_path / "test.sqlite3"
    store = ProjectStore(Database(db_path))
    real = store.create_sample(project_id=project_id, source_kind="local", status="analyzed")
    store.update_sample(
        real["id"],
        structure=_sample_structure(project_id, real["id"], marker="real"),
    )

    response = client.post(
        f"/api/projects/{project_id}/structure-from-knowledge",
        json={"entryId": entry_id, "applyStructure": True},
    )
    assert response.status_code == 400
    assert "reference only" in response.json()["detail"]


def test_user_override_not_overwritten_by_ensure(client: TestClient, tmp_path: Path) -> None:
    project_id = _create_project(client)
    sample_a = str(uuid.uuid4())
    sample_b = str(uuid.uuid4())
    _write_draft(tmp_path, project_id, sample_a, marker="A")
    _write_draft(tmp_path, project_id, sample_b, marker="B")
    entry_a = _promote_entry(client, project_id, sample_a)
    entry_b = _promote_entry(client, project_id, sample_b)

    client.post(
        f"/api/projects/{project_id}/brief",
        json={"topic": "电商带货", "sellingPoints": [], "mustMention": [], "avoidMention": []},
    )

    override = client.put(
        f"/api/projects/{project_id}/knowledge/selection",
        json={"primaryEntryId": entry_b, "referenceEntryIds": [], "applyStructure": False},
    )
    assert override.status_code == 200
    assert override.json()["selection"]["mode"] == "user_override"

    client.post(f"/api/projects/{project_id}/brief", json={"topic": "完全不同主题"})
    selection = client.get(f"/api/projects/{project_id}/knowledge/selection")
    assert selection.json()["selection"]["primaryEntryId"] == entry_b
    assert selection.json()["selection"]["mode"] == "user_override"
    assert entry_a != entry_b


def test_promote_draft_is_idempotent(client: TestClient, tmp_path: Path) -> None:
    project_id = _create_project(client)
    sample_id = str(uuid.uuid4())
    _write_draft(tmp_path, project_id, sample_id)

    first = client.post(
        f"/api/projects/{project_id}/samples/{sample_id}/knowledge/promote",
        json={
            "title": "电商促销",
            "category": "电商带货",
            "style": "快节奏促销",
            "hookType": "pain_point",
        },
    )
    second = client.post(
        f"/api/projects/{project_id}/samples/{sample_id}/knowledge/promote",
        json={
            "title": "电商促销",
            "category": "电商带货",
            "style": "快节奏促销",
            "hookType": "pain_point",
        },
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["entry"]["id"] == second.json()["entry"]["id"]

    listing = client.get("/api/knowledge/entries")
    matching = [
        item
        for item in listing.json()["entries"]
        if item.get("sourceSampleId") == sample_id
    ]
    assert len(matching) == 1


def test_generation_plan_uses_payload_brief(client: TestClient, tmp_path: Path) -> None:
    project_id = _create_project(client)
    sample_id = str(uuid.uuid4())
    _write_draft(tmp_path, project_id, sample_id)
    entry_id = _promote_entry(client, project_id, sample_id)

    client.post(
        f"/api/projects/{project_id}/brief",
        json={"topic": "教育科普", "sellingPoints": [], "mustMention": [], "avoidMention": []},
    )

    generation = client.post(
        f"/api/projects/{project_id}/generation-plan",
        json={"brief": {"topic": "电商带货", "sellingPoints": ["优惠"], "mustMention": [], "avoidMention": []}},
    )
    assert generation.status_code == 201, generation.text

    selection = client.get(f"/api/projects/{project_id}/knowledge/selection")
    assert selection.json()["selection"]["primaryEntryId"] == entry_id


def test_enrich_entry_repairs_corrupted_metadata(client: TestClient, tmp_path: Path) -> None:
    project_id = _create_project(client)
    sample_id = str(uuid.uuid4())
    draft_root = (
        tmp_path
        / "storage"
        / "projects"
        / project_id
        / "knowledge"
        / "drafts"
        / sample_id
    )
    draft_root.mkdir(parents=True, exist_ok=True)
    skill_md = """---
title: 问题-解决方案短视频结构
category: 通用短视频
style: 标准结构
summary: 通过钩子引入问题，快速展示解决方案并引导行动。
hookType: engaging opening
tempo: mixed
durationBucket: short
slotPattern: hook→problem→solution→cta
---

## 适用场景
测试
"""
    (draft_root / "structure-skill.md").write_text(skill_md, encoding="utf-8")
    (draft_root / "video-structure.json").write_text(
        json.dumps(_sample_structure(project_id, sample_id, marker="marker")),
        encoding="utf-8",
    )
    (draft_root / "entry-meta.json").write_text(
        json.dumps(
            {
                "title": "??????",
                "category": "?????",
                "style": "????",
                "summary": "??????",
            }
        ),
        encoding="utf-8",
    )

    promote = client.post(
        f"/api/projects/{project_id}/samples/{sample_id}/knowledge/promote",
        json={"title": "??????", "category": "?????", "style": "????"},
    )
    assert promote.status_code == 200
    entry_id = promote.json()["entry"]["id"]

    fetched = client.get(f"/api/knowledge/entries/{entry_id}")
    assert fetched.status_code == 200
    body = fetched.json()
    assert body["title"] == "问题-解决方案短视频结构"
    assert body["category"] == "通用短视频"
    assert "????" not in body["summary"]
