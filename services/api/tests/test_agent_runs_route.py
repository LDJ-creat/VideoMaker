from __future__ import annotations

import json
from pathlib import Path

from app.db.session import Database, initialize_database
from app.main import create_app
from app.services.project_store import ProjectStore
from fastapi.testclient import TestClient


def _seed_generation(
    *,
    database_path: Path,
    storage_root: Path,
) -> tuple[str, str]:
    database = Database(database_path)
    initialize_database(database)
    store = ProjectStore(database)
    project = store.create_project("Test Project")
    project_id = project["id"]
    generation = store.create_generation(
        project_id=project_id,
        task_id="task-1",
        status="succeeded",
    )
    generation_id = generation["id"]

    log_dir = storage_root / "projects" / project_id / "logs" / "agent-runs"
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / "run-1.json").write_text(
        json.dumps(
            {
                "id": "run-1",
                "generationId": generation_id,
                "agentName": "structure_analyst",
                "model": "gpt-4o",
                "promptVersion": "a1b2c3d4",
                "task": "structure_analyst",
                "inputSummary": "{}",
                "outputValid": True,
                "latencyMs": 1200,
                "createdAt": "2026-05-29T12:00:00Z",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (log_dir / "run-other-gen.json").write_text(
        json.dumps(
            {
                "id": "run-other",
                "generationId": "other-gen",
                "agentName": "slot_mapper",
                "model": "gpt-4o",
                "promptVersion": "deadbeef",
                "task": "slot_mapper",
                "inputSummary": "{}",
                "outputValid": True,
                "latencyMs": 900,
                "createdAt": "2026-05-29T12:01:00Z",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return project_id, generation_id


def test_agent_runs_returns_logs_for_generation(tmp_path: Path) -> None:
    database_path = tmp_path / "videomaker.sqlite3"
    storage_root = tmp_path / "storage"
    _project_id, generation_id = _seed_generation(
        database_path=database_path,
        storage_root=storage_root,
    )

    app = create_app(database_path=database_path, storage_root=storage_root)
    client = TestClient(app)

    response = client.get(f"/api/generations/{generation_id}/agent-runs")

    assert response.status_code == 200
    payload = response.json()
    assert payload == {
        "runs": [
            {
                "id": "run-1",
                "agentName": "structure_analyst",
                "model": "gpt-4o",
                "promptVersion": "a1b2c3d4",
                "outputValid": True,
                "latencyMs": 1200.0,
                "createdAt": "2026-05-29T12:00:00Z",
            }
        ]
    }


def test_agent_runs_returns_empty_when_no_logs(tmp_path: Path) -> None:
    database_path = tmp_path / "videomaker.sqlite3"
    storage_root = tmp_path / "storage"
    project_id, generation_id = _seed_generation(
        database_path=database_path,
        storage_root=storage_root,
    )
    log_dir = storage_root / "projects" / project_id / "logs" / "agent-runs"
    for path in log_dir.glob("*.json"):
        path.unlink()

    app = create_app(database_path=database_path, storage_root=storage_root)
    client = TestClient(app)

    response = client.get(f"/api/generations/{generation_id}/agent-runs")

    assert response.status_code == 200
    assert response.json() == {"runs": []}


def test_agent_runs_404_for_unknown_generation(tmp_path: Path) -> None:
    database_path = tmp_path / "videomaker.sqlite3"
    storage_root = tmp_path / "storage"
    app = create_app(database_path=database_path, storage_root=storage_root)
    client = TestClient(app)

    response = client.get("/api/generations/missing/agent-runs")

    assert response.status_code == 404


def test_agent_runs_skips_malformed_log_files(tmp_path: Path) -> None:
    database_path = tmp_path / "videomaker.sqlite3"
    storage_root = tmp_path / "storage"
    project_id, generation_id = _seed_generation(
        database_path=database_path,
        storage_root=storage_root,
    )
    log_dir = storage_root / "projects" / project_id / "logs" / "agent-runs"
    (log_dir / "broken.json").write_text('{"generationId": "' + generation_id + '"}', encoding="utf-8")

    app = create_app(database_path=database_path, storage_root=storage_root)
    client = TestClient(app)

    response = client.get(f"/api/generations/{generation_id}/agent-runs")

    assert response.status_code == 200
    assert len(response.json()["runs"]) == 1
    assert response.json()["runs"][0]["id"] == "run-1"
