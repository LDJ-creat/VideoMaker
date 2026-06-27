from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

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
    response = client.post("/api/projects", json={"name": "Delete test"})
    assert response.status_code == 201
    return response.json()["id"]


def test_delete_generation_removes_db_rows_and_storage(client: TestClient) -> None:
    project_id = _create_project(client)
    storage_root: Path = client.app.state.storage_root  # type: ignore[attr-defined]
    store = ProjectStore(client.app.state.db)  # type: ignore[attr-defined]

    source = store.create_generation(
        project_id=project_id,
        task_id="task-source",
        status="succeeded",
        variant="high_conversion",
    )
    source_id = source["id"]
    fork = store.create_generation(
        project_id=project_id,
        task_id="task-fork",
        status="succeeded",
        variant="high_conversion",
    )
    fork_id = fork["id"]

    source_root = storage_root / "projects" / project_id / "generations" / source_id
    fork_root = storage_root / "projects" / project_id / "generations" / fork_id
    source_root.mkdir(parents=True)
    fork_root.mkdir(parents=True)
    (source_root / "generation-plan.json").write_text(
        json.dumps({"id": source_id, "variant": "high_conversion"}),
        encoding="utf-8",
    )
    (fork_root / "revise-context.json").write_text(
        json.dumps({"sourceGenerationId": source_id, "instruction": "center card"}),
        encoding="utf-8",
    )
    render_root = storage_root / "projects" / project_id / "renders" / fork_id
    render_root.mkdir(parents=True)
    (render_root / "output.mp4").write_bytes(b"fake-mp4")

    response = client.delete(f"/api/projects/{project_id}/generations/{fork_id}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["deletedGenerationIds"] == [fork_id]
    assert store.get_generation(fork_id) is None
    assert not fork_root.exists()
    assert not render_root.exists()
    assert store.get_generation(source_id) is not None


def test_delete_generation_cascades_revise_forks(client: TestClient) -> None:
    project_id = _create_project(client)
    storage_root: Path = client.app.state.storage_root  # type: ignore[attr-defined]
    store = ProjectStore(client.app.state.db)  # type: ignore[attr-defined]

    source = store.create_generation(
        project_id=project_id,
        task_id="task-source",
        status="succeeded",
        variant="high_conversion",
    )
    source_id = source["id"]
    fork = store.create_generation(
        project_id=project_id,
        task_id="task-fork",
        status="succeeded",
        variant="high_conversion",
    )
    fork_id = fork["id"]

    source_root = storage_root / "projects" / project_id / "generations" / source_id
    fork_root = storage_root / "projects" / project_id / "generations" / fork_id
    source_root.mkdir(parents=True)
    fork_root.mkdir(parents=True)
    (fork_root / "revise-context.json").write_text(
        json.dumps({"sourceGenerationId": source_id}),
        encoding="utf-8",
    )

    response = client.delete(f"/api/projects/{project_id}/generations/{source_id}")
    assert response.status_code == 200
    deleted = set(response.json()["deletedGenerationIds"])
    assert deleted == {source_id, fork_id}
    assert store.get_generation(source_id) is None
    assert store.get_generation(fork_id) is None
