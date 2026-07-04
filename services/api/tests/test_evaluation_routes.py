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
    response = client.post("/api/projects", json={"name": "Evaluation Test"})
    assert response.status_code == 201
    return response.json()["id"]


def _seed_generation_artifacts(
    storage_root: Path,
    project_id: str,
    generation_id: str,
) -> None:
    root = storage_root / "projects" / project_id / "generations" / generation_id
    root.mkdir(parents=True, exist_ok=True)
    (root / "generation-plan.json").write_text(
        json.dumps({"id": generation_id, "projectId": project_id, "timeline": {"durationSec": 15}}),
        encoding="utf-8",
    )
    (root / "gap-report.json").write_text(json.dumps({"slots": []}), encoding="utf-8")
    (root / "checkpoint.json").write_text(
        json.dumps({"generationId": generation_id, "stageTimings": []}),
        encoding="utf-8",
    )
    log_dir = storage_root / "projects" / project_id / "logs" / "model-calls"
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / "call-1.json").write_text(
        json.dumps(
            {
                "id": "call-1",
                "callKind": "chat_json",
                "profile": "text",
                "model": "m",
                "driver": "openai_compatible",
                "outputValid": True,
                "latencyMs": 10,
                "createdAt": "2026-07-04T00:00:00Z",
                "generationId": generation_id,
                "usageUnits": {"kind": "tokens", "prompt": 1, "completion": 2, "total": 3},
            }
        ),
        encoding="utf-8",
    )


def _insert_generation(
    client: TestClient,
    *,
    project_id: str,
    generation_id: str,
) -> None:
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
            (
                generation_id,
                project_id,
                "s1",
                "i1",
                "{}",
                "{}",
                "succeeded",
                "task-1",
                "high_click",
                now,
                now,
            ),
        )
        connection.commit()


def test_get_evaluation_lazy_build(client: TestClient, tmp_path: Path) -> None:
    project_id = _create_project(client)
    storage_root: Path = client.app.state.storage_root
    generation_id = "gen-eval"
    _seed_generation_artifacts(storage_root, project_id, generation_id)
    _insert_generation(client, project_id=project_id, generation_id=generation_id)

    response = client.get(f"/api/generations/{generation_id}/evaluation")
    assert response.status_code == 200
    body = response.json()
    assert body["report"]["generationId"] == generation_id
    report_path = (
        storage_root / "projects" / project_id / "generations" / generation_id / "evaluation-report.json"
    )
    assert report_path.is_file()


def test_rebuild_evaluation(client: TestClient, tmp_path: Path) -> None:
    project_id = _create_project(client)
    storage_root: Path = client.app.state.storage_root
    generation_id = "gen-rebuild"
    _seed_generation_artifacts(storage_root, project_id, generation_id)
    _insert_generation(client, project_id=project_id, generation_id=generation_id)

    report_path = (
        storage_root / "projects" / project_id / "generations" / generation_id / "evaluation-report.json"
    )
    report_path.write_text(json.dumps({"version": "1.0", "stale": True}), encoding="utf-8")

    response = client.post(f"/api/generations/{generation_id}/evaluation/rebuild")
    assert response.status_code == 200
    body = response.json()
    assert body.get("rebuilt") is True
    assert "stale" not in body["report"]
