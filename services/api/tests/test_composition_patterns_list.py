from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services.task_events import now_iso


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    db_path = tmp_path / "test.sqlite3"
    storage_root = tmp_path / "storage"
    storage_root.mkdir(parents=True, exist_ok=True)
    app = create_app(database_path=db_path, storage_root=storage_root, sync_pipelines=True)
    return TestClient(app)


def _create_project(client: TestClient) -> str:
    response = client.post("/api/projects", json={"name": "Composition List Test"})
    assert response.status_code == 201
    return response.json()["id"]


def _seed_draft(storage_root: Path, project_id: str, generation_id: str, slot_id: str) -> None:
    draft = (
        storage_root
        / "projects"
        / project_id
        / "knowledge"
        / "drafts"
        / "composition"
        / generation_id
        / slot_id
    )
    draft.mkdir(parents=True)
    (draft / "composition-skill.md").write_text("# skill", encoding="utf-8")
    (draft / "spec.template.json").write_text(
        json.dumps(
            {
                "template": "composition",
                "durationSec": 2,
                "composition": {"bodyHtml": '<div id="root">x</div>'},
            }
        ),
        encoding="utf-8",
    )
    (draft / "entry-meta.json").write_text(
        json.dumps({"entryKind": "composition_pattern", "slotRoles": ["benefit_card"], "lintPassed": True}),
        encoding="utf-8",
    )
    (draft / "provenance.json").write_text(json.dumps({"lintPassed": True}), encoding="utf-8")
    (draft / "lint-log.json").write_text(json.dumps({"ok": True}), encoding="utf-8")
    gen_root = storage_root / "projects" / project_id / "generations" / generation_id
    gen_root.mkdir(parents=True, exist_ok=True)
    (gen_root / "generation-plan.json").write_text(
        json.dumps(
            {
                "storyboard": [
                    {
                        "slotId": slot_id,
                        "role": "benefit_card",
                        "scriptIntent": "核心卖点",
                    }
                ],
                "completionActions": [
                    {"id": "action-1", "slotId": slot_id, "provider": "hyperframes_material"},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_list_composition_patterns_requires_generation(client: TestClient) -> None:
    response = client.get("/api/generations/missing-gen/composition-patterns")
    assert response.status_code == 404


def test_list_composition_patterns_returns_drafts(client: TestClient, tmp_path: Path) -> None:
    project_id = _create_project(client)
    storage_root = tmp_path / "storage"
    generation_id = "gen-1"
    slot_id = "slot-1"
    _seed_draft(storage_root, project_id, generation_id, slot_id)

    now = now_iso()
    with client.app.state.db.connect() as connection:
        connection.execute(
            """
            INSERT INTO generations (
              id, project_id, structure_id, inventory_id, gap_report_json, plan_json,
              status, task_id, variant, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (generation_id, project_id, "s1", "i1", "{}", "{}", "succeeded", "task-1", "high_click", now, now),
        )
        connection.commit()

    response = client.get(f"/api/generations/{generation_id}/composition-patterns")
    assert response.status_code == 200
    body = response.json()
    assert body["generationId"] == generation_id
    assert len(body["patterns"]) == 1
    assert body["patterns"][0]["slotId"] == slot_id
    assert body["patterns"][0]["slotRole"] == "benefit_card"
