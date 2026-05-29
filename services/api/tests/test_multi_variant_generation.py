from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.test_p0_flow_routes import FakeDemoPipeline


@pytest.fixture()
def variant_client(app_paths):
    from app.main import create_app
    from app.services.pipeline_runner import PipelineRunner
    from app.services.project_store import ProjectStore
    from app.services.task_events import TaskEventService

    database_path = app_paths["database_path"]
    storage_root = app_paths["storage_root"]
    from app.db.session import Database

    database = Database(database_path)
    task_events = TaskEventService(database)
    project_store = ProjectStore(database)
    runner = PipelineRunner(
        database=database,
        storage_root=storage_root,
        task_events=task_events,
        project_store=project_store,
        sync=True,
        pipeline=FakeDemoPipeline(),
    )
    app = create_app(
        database_path=database_path,
        storage_root=storage_root,
        sync_pipelines=True,
        pipeline_runner=runner,
    )
    return TestClient(app)


def _prepare_project_with_structure(client: TestClient, tmp_path: Path) -> dict[str, Any]:
    project = client.post("/api/projects", json={"name": "MultiVariant"}).json()
    video = tmp_path / "sample.mp4"
    video.write_bytes(b"fake-video")
    sample_id = client.post(
        f"/api/projects/{project['id']}/samples/upload",
        files={"file": ("sample.mp4", video.read_bytes(), "video/mp4")},
    ).json()["id"]
    client.post(f"/api/samples/{sample_id}/analyze")
    return project


def test_generation_plan_defaults_to_two_variants(variant_client: TestClient, tmp_path: Path) -> None:
    project = _prepare_project_with_structure(variant_client, tmp_path)

    response = variant_client.post(f"/api/projects/{project['id']}/generation-plan")
    assert response.status_code == 201
    body = response.json()
    assert len(body["generations"]) == 2
    assert [entry["variant"] for entry in body["generations"]] == ["high_click", "high_conversion"]
    assert body["generations"][0]["label"] == "高点击版"
    assert body["generations"][1]["label"] == "高转化版"


def test_generation_plan_empty_body_still_spawns_two_tasks(
    variant_client: TestClient,
    tmp_path: Path,
) -> None:
    project = _prepare_project_with_structure(variant_client, tmp_path)

    response = variant_client.post(
        f"/api/projects/{project['id']}/generation-plan",
        json={},
    )
    assert response.status_code == 201
    generations = response.json()["generations"]
    task_ids = {entry["taskId"] for entry in generations}
    generation_ids = {entry["generationId"] for entry in generations}
    assert len(task_ids) == 2
    assert len(generation_ids) == 2


def test_generation_plan_rejects_unknown_variant(variant_client: TestClient, tmp_path: Path) -> None:
    project = _prepare_project_with_structure(variant_client, tmp_path)

    response = variant_client.post(
        f"/api/projects/{project['id']}/generation-plan",
        json={"variants": ["not_a_variant"]},
    )
    assert response.status_code == 400
    assert "Unknown variant" in response.json()["detail"]


def test_generation_plan_rejects_disabled_variant(variant_client: TestClient, tmp_path: Path) -> None:
    project = _prepare_project_with_structure(variant_client, tmp_path)

    response = variant_client.post(
        f"/api/projects/{project['id']}/generation-plan",
        json={"variants": ["fast_paced"]},
    )
    assert response.status_code == 400
    assert "disabled" in response.json()["detail"].lower()


def test_generation_plan_rejects_duplicate_variant(variant_client: TestClient, tmp_path: Path) -> None:
    project = _prepare_project_with_structure(variant_client, tmp_path)

    response = variant_client.post(
        f"/api/projects/{project['id']}/generation-plan",
        json={"variants": ["high_click", "high_click"]},
    )
    assert response.status_code == 400
    assert "Duplicate variant" in response.json()["detail"]


def test_latest_generations_follow_default_variant_order(
    variant_client: TestClient,
    tmp_path: Path,
) -> None:
    project = _prepare_project_with_structure(variant_client, tmp_path)
    variant_client.post(f"/api/projects/{project['id']}/generation-plan")

    latest = variant_client.get(f"/api/projects/{project['id']}/generations/latest")
    assert latest.status_code == 200
    variants = [entry["variant"] for entry in latest.json()["generations"]]
    assert variants == ["high_click", "high_conversion"]


def test_generation_plan_single_variant(variant_client: TestClient, tmp_path: Path) -> None:
    project = _prepare_project_with_structure(variant_client, tmp_path)

    response = variant_client.post(
        f"/api/projects/{project['id']}/generation-plan",
        json={"variants": ["high_click"]},
    )
    assert response.status_code == 201
    generations = response.json()["generations"]
    assert len(generations) == 1
    assert generations[0]["variant"] == "high_click"


def test_generation_retry_preserves_variant(
    variant_client: TestClient,
    tmp_path: Path,
    app_paths,
) -> None:
    project = _prepare_project_with_structure(variant_client, tmp_path)
    created = variant_client.post(
        f"/api/projects/{project['id']}/generation-plan",
        json={"variants": ["high_conversion"]},
    ).json()
    task_id = created["generations"][0]["taskId"]

    from app.db.session import Database

    database = Database(app_paths["database_path"])
    with database.connect() as connection:
        connection.execute(
            "UPDATE tasks SET status = ?, stage = ?, progress = ?, message = ?, error_json = ? WHERE id = ?",
            (
                "failed",
                "analyzing_assets",
                10,
                "forced failure",
                '{"code":"generation_failed","message":"boom","retryable":true}',
                task_id,
            ),
        )

    FakeDemoPipeline.last_variant = "default"
    retry = variant_client.post(f"/api/tasks/{task_id}/retry")
    assert retry.status_code == 200
    assert FakeDemoPipeline.last_variant == "high_conversion"


def test_latest_generations_returns_one_entry_per_variant(
    variant_client: TestClient,
    tmp_path: Path,
) -> None:
    project = _prepare_project_with_structure(variant_client, tmp_path)
    created = variant_client.post(f"/api/projects/{project['id']}/generation-plan").json()

    latest = variant_client.get(f"/api/projects/{project['id']}/generations/latest")
    assert latest.status_code == 200
    entries = latest.json()["generations"]
    assert len(entries) == 2
    by_variant = {entry["variant"]: entry for entry in entries}
    for requested in created["generations"]:
        entry = by_variant[requested["variant"]]
        assert entry["generationId"] == requested["generationId"]
        assert entry["plan"]["variant"] == requested["variant"]
        assert entry["plan"].get("gapReport") is not None
