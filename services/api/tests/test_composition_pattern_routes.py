from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services.task_events import now_iso


@pytest.fixture(autouse=True)
def enable_fixture_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIDEOMAKER_FIXTURE_MODE", "true")


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


def _seed_promote_fixtures(
    storage_root: Path,
    project_id: str,
    generation_id: str,
    slot_id: str,
) -> None:
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


def test_composition_promote_requires_confirm(client: TestClient, tmp_path: Path) -> None:
    project_id = _create_project(client)
    response = client.post(
        f"/api/projects/{project_id}/knowledge/composition/promote",
        json={
            "generationId": "gen-1",
            "slotId": "slot-1",
            "confirm": False,
        },
    )
    assert response.status_code == 422


def test_composition_promote_publishes_pattern(client: TestClient, tmp_path: Path) -> None:
    project_id = _create_project(client)
    storage_root = tmp_path / "storage"
    generation_id = "gen-1"
    slot_id = "slot-1"
    _seed_promote_fixtures(storage_root, project_id, generation_id, slot_id)

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

    response = client.post(
        f"/api/projects/{project_id}/knowledge/composition/promote",
        json={
            "generationId": generation_id,
            "slotId": slot_id,
            "confirm": True,
        },
    )
    assert response.status_code == 200, response.text
    entry = response.json()["entry"]
    assert entry["entryKind"] == "composition_pattern"
    assert entry["id"] == f"comp-{generation_id}-{slot_id}"

    published = (
        storage_root
        / "knowledge"
        / "composition"
        / f"comp-{generation_id}-{slot_id}"
    )
    assert (published / "spec.template.json").is_file()
    assert (published / "spec.instance.json").is_file()
    assert (published / "composition-skill.md").is_file()


def test_composition_promote_rejects_path_traversal_ids(client: TestClient) -> None:
    project_id = _create_project(client)
    response = client.post(
        f"/api/projects/{project_id}/knowledge/composition/promote",
        json={
            "generationId": "../evil",
            "slotId": "slot-1",
            "confirm": True,
        },
    )
    assert response.status_code == 422
    assert "invalid_generation_id" in response.json()["detail"]


def test_composition_promote_rejects_generation_project_mismatch(
    client: TestClient, tmp_path: Path
) -> None:
    project_id = _create_project(client)
    other_project = _create_project(client)
    storage_root = tmp_path / "storage"
    generation_id = "gen-1"
    slot_id = "slot-1"
    _seed_promote_fixtures(storage_root, project_id, generation_id, slot_id)

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

    response = client.post(
        f"/api/projects/{other_project}/knowledge/composition/promote",
        json={
            "generationId": generation_id,
            "slotId": slot_id,
            "confirm": True,
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "generation_project_mismatch"


def test_composition_promote_surfaces_prepare_error(client: TestClient, tmp_path: Path) -> None:
    project_id = _create_project(client)
    storage_root = tmp_path / "storage"
    generation_id = "gen-1"
    slot_id = "slot-1"
    _seed_promote_fixtures(storage_root, project_id, generation_id, slot_id)

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

    def _failed_prepare(**kwargs: object) -> dict[str, object]:
        return {
            "ok": False,
            "finalEvent": {
                "status": "failed",
                "error": {"code": "generalization_lint_failed", "message": "generalization_lint_failed"},
            },
        }

    client.app.state.pipeline_runner.run_composition_pattern_promote = _failed_prepare  # type: ignore[method-assign]

    response = client.post(
        f"/api/projects/{project_id}/knowledge/composition/promote",
        json={
            "generationId": generation_id,
            "slotId": slot_id,
            "confirm": True,
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "generalization_lint_failed"


def test_composition_promote_idempotent_republish(client: TestClient, tmp_path: Path) -> None:
    project_id = _create_project(client)
    storage_root = tmp_path / "storage"
    generation_id = "gen-1"
    slot_id = "slot-1"
    _seed_promote_fixtures(storage_root, project_id, generation_id, slot_id)

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

    body = {
        "generationId": generation_id,
        "slotId": slot_id,
        "confirm": True,
    }
    first = client.post(f"/api/projects/{project_id}/knowledge/composition/promote", json=body)
    second = client.post(f"/api/projects/{project_id}/knowledge/composition/promote", json=body)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["entry"]["id"] == second.json()["entry"]["id"]
