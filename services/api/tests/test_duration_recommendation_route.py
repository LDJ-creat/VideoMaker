from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.test_p0_flow_routes import FakeDemoPipeline


@pytest.fixture()
def api_client(app_paths):
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


def _prepare_analyzed_sample(client: TestClient, tmp_path: Path) -> tuple[dict, str]:
    project = client.post("/api/projects", json={"name": "Duration"}).json()
    video = tmp_path / "sample.mp4"
    video.write_bytes(b"fake-video")
    sample_id = client.post(
        f"/api/projects/{project['id']}/samples/upload",
        files={"file": ("sample.mp4", video.read_bytes(), "video/mp4")},
    ).json()["id"]
    client.post(f"/api/samples/{sample_id}/analyze")
    return project, sample_id


def test_duration_recommendation_after_sample_analysis(
    api_client: TestClient,
    tmp_path: Path,
) -> None:
    project, _sample_id = _prepare_analyzed_sample(api_client, tmp_path)

    response = api_client.get(f"/api/projects/{project['id']}/duration-recommendation")
    assert response.status_code == 200
    body = response.json()
    assert body["recommendedSec"] == 10.0
    assert body["defaultTargetSec"] == 10.0
    assert body["maxTargetSec"] == 600
    assert "shortFormMaxSec" not in body


def test_duration_recommendation_defaults_without_structure(
    api_client: TestClient,
) -> None:
    project = api_client.post("/api/projects", json={"name": "NoSample"}).json()
    response = api_client.get(f"/api/projects/{project['id']}/duration-recommendation")
    assert response.status_code == 200
    body = response.json()
    assert body["recommendedSec"] == 30.0
    assert body["defaultTargetSec"] == 30.0
