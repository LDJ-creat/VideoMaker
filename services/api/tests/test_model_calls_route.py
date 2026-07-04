from __future__ import annotations

import json
from pathlib import Path

from app.db.session import Database, initialize_database
from app.main import create_app
from app.services.project_store import ProjectStore
from app.services.task_events import TaskEventService
from fastapi.testclient import TestClient


def _seed_generation_with_model_calls(
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

    log_dir = storage_root / "projects" / project_id / "logs" / "model-calls"
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / "call-1.json").write_text(
        json.dumps(
            {
                "id": "call-1",
                "callKind": "chat_json",
                "profile": "text",
                "model": "gpt-test",
                "driver": "openai_compatible",
                "generationId": generation_id,
                "taskId": "task-1",
                "outputValid": True,
                "latencyMs": 10.0,
                "createdAt": "2026-06-19T12:00:00Z",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (log_dir / "call-other.json").write_text(
        json.dumps(
            {
                "id": "call-other",
                "callKind": "image",
                "profile": "image",
                "model": "dall-e-3",
                "driver": "openai_compatible",
                "generationId": "other-gen",
                "outputValid": True,
                "latencyMs": 20.0,
                "createdAt": "2026-06-19T12:01:00Z",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return project_id, generation_id


def test_model_calls_returns_logs_for_generation(tmp_path: Path) -> None:
    database_path = tmp_path / "videomaker.sqlite3"
    storage_root = tmp_path / "storage"
    _project_id, generation_id = _seed_generation_with_model_calls(
        database_path=database_path,
        storage_root=storage_root,
    )

    app = create_app(database_path=database_path, storage_root=storage_root)
    client = TestClient(app)

    response = client.get(f"/api/generations/{generation_id}/model-calls?kind=chat")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["calls"]) == 1
    assert payload["calls"][0]["callKind"] == "chat_json"


def test_model_calls_returns_logs_for_task(tmp_path: Path) -> None:
    database_path = tmp_path / "videomaker.sqlite3"
    storage_root = tmp_path / "storage"
    database = Database(database_path)
    initialize_database(database)
    store = ProjectStore(database)
    project = store.create_project("Test Project")
    project_id = project["id"]

    task_service = TaskEventService(database)
    task = task_service.create_task(
        project_id=project_id,
        stage="analyze",
        message="start",
    )
    task_id = task["taskId"]

    log_dir = storage_root / "projects" / project_id / "logs" / "model-calls"
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / "call-2.json").write_text(
        json.dumps(
            {
                "id": "call-2",
                "callKind": "image",
                "profile": "image",
                "model": "dall-e-3",
                "driver": "openai_compatible",
                "taskId": task_id,
                "outputValid": True,
                "latencyMs": 20.0,
                "createdAt": "2026-06-19T12:01:00Z",
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    app = create_app(database_path=database_path, storage_root=storage_root)
    client = TestClient(app)

    response = client.get(f"/api/tasks/{task_id}/model-calls?kind=image")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["calls"]) == 1
    assert payload["calls"][0]["callKind"] == "image"
