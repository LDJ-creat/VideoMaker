from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.services.artifact_store import ArtifactStore


def _create_project(client: TestClient) -> str:
    return client.post("/api/projects", json={"name": "Media"}).json()["id"]


def test_stream_project_media_file(client: TestClient, app_paths) -> None:
    project_id = _create_project(client)
    relative_path = "generations/gen-1/material/hook.png"
    file_path = (
        app_paths["storage_root"] / "projects" / project_id / relative_path
    )
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_bytes(b"fake-png")

    response = client.get(f"/api/projects/{project_id}/media/file/{relative_path}")

    assert response.status_code == 200
    assert response.content == b"fake-png"


def test_stream_project_media_file_missing_returns_404(client: TestClient) -> None:
    project_id = _create_project(client)

    response = client.get(
        f"/api/projects/{project_id}/media/file/generations/missing.png",
    )

    assert response.status_code == 404


def test_resolve_project_path_rejects_traversal(app_paths) -> None:
    store = ArtifactStore(app_paths["storage_root"])

    with pytest.raises(ValueError, match="outside project storage"):
        store.resolve_project_path("project-1", "../escape.txt")


def test_stream_project_artifact_media(client: TestClient, app) -> None:
    project_id = _create_project(client)
    store = ArtifactStore(app.state.storage_root)
    artifact = store.register_artifact(
        app.state.db,
        project_id=project_id,
        task_id="task-1",
        artifact_type="image",
        relative_path="generations/gen-1/material/hook.png",
    )
    path = store.resolve_project_path(
        project_id,
        "generations/gen-1/material/hook.png",
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"artifact-bytes")

    response = client.get(
        f"/api/projects/{project_id}/media/artifacts/{artifact['id']}",
    )

    assert response.status_code == 200
    assert response.content == b"artifact-bytes"
