from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    db_path = tmp_path / "test.sqlite3"
    storage_root = tmp_path / "storage"
    storage_root.mkdir(parents=True, exist_ok=True)
    app = create_app(database_path=db_path, storage_root=storage_root, sync_pipelines=True)
    return TestClient(app)


def _create_project(client: TestClient) -> str:
    response = client.post("/api/projects", json={"name": "Composition Pattern Test"})
    assert response.status_code == 201
    return response.json()["id"]


def test_composition_promote_requires_confirm(client: TestClient, tmp_path: Path) -> None:
    project_id = _create_project(client)
    response = client.post(
        f"/api/projects/{project_id}/knowledge/composition/promote",
        json={
            "generationId": "gen-1",
            "slotId": "slot-1",
            "userScore": 5,
            "confirm": False,
        },
    )
    assert response.status_code == 422


def test_composition_promote_requires_lint_log(client: TestClient, tmp_path: Path) -> None:
    project_id = _create_project(client)
    storage_root = tmp_path / "storage"
    draft = (
        storage_root
        / "projects"
        / project_id
        / "knowledge"
        / "drafts"
        / "composition"
        / "gen-1"
        / "slot-1"
    )
    draft.mkdir(parents=True)
    (draft / "composition-skill.md").write_text("# skill", encoding="utf-8")
    (draft / "spec.template.json").write_text("{}", encoding="utf-8")
    (draft / "entry-meta.json").write_text(
        json.dumps({"entryKind": "composition_pattern", "slotRoles": ["benefit_card"], "lintPassed": True}),
        encoding="utf-8",
    )
    (draft / "provenance.json").write_text(json.dumps({"lintPassed": True}), encoding="utf-8")
    (draft / "lint-log.json").write_text(json.dumps({"ok": True}), encoding="utf-8")

    response = client.post(
        f"/api/projects/{project_id}/knowledge/composition/promote",
        json={
            "generationId": "gen-1",
            "slotId": "slot-1",
            "userScore": 5,
            "confirm": True,
            "title": "My Pattern",
        },
    )
    assert response.status_code == 200
    entry = response.json()["entry"]
    assert entry["entryKind"] == "composition_pattern"
    assert entry["title"] == "My Pattern"
