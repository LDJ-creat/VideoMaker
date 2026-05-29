import pytest

from app.services.artifact_store import ArtifactStore


def test_project_path_resolves_under_storage_root(app_paths):
    store = ArtifactStore(app_paths["storage_root"])

    project_root = store.project_root("project-1")

    assert project_root == app_paths["storage_root"] / "projects" / "project-1"
    assert project_root.exists()


def test_rejects_path_traversal(app_paths):
    store = ArtifactStore(app_paths["storage_root"])

    with pytest.raises(ValueError, match="outside project storage"):
        store.resolve_project_path("project-1", "../escape.txt")


def test_register_artifact_persists_record(app):
    store = ArtifactStore(app.state.storage_root)

    artifact = store.register_artifact(
        app.state.db,
        project_id="project-1",
        task_id="task-1",
        artifact_type="json",
        relative_path="artifacts/result.json",
    )

    assert artifact["id"]
    assert artifact["type"] == "json"
    assert artifact["uri"].endswith("storage/projects/project-1/artifacts/result.json")


def test_get_artifact_returns_record(app):
    store = ArtifactStore(app.state.storage_root)
    created = store.register_artifact(
        app.state.db,
        project_id="project-1",
        task_id="task-1",
        artifact_type="json",
        relative_path="artifacts/lookup.json",
    )

    fetched = store.get_artifact(
        app.state.db,
        artifact_id=created["id"],
        project_id="project-1",
    )

    assert fetched is not None
    assert fetched["id"] == created["id"]
    assert fetched["type"] == "json"
