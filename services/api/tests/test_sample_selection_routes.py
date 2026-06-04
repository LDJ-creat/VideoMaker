from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services.pipeline_runner import PipelineRunner
from app.services.project_store import ProjectStore
from app.services.task_events import TaskEventService
from app.services.upload_batch_store import UploadBatchStore
from tests.test_p0_flow_routes import FakeDemoPipeline


class MixedResultPipeline(FakeDemoPipeline):
    def run_generation(self, *, emit, variant: str = "default", **kwargs):  # type: ignore[no-untyped-def]
        if variant == "high_conversion":
            emit(
                status="failed",
                stage="analyzing_assets",
                progress=0,
                message="failed variant",
            )
            return {"ok": False}
        return super().run_generation(emit=emit, variant=variant, **kwargs)


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    db_path = tmp_path / "test.sqlite3"
    storage_root = tmp_path / "storage"
    storage_root.mkdir(parents=True, exist_ok=True)
    app = create_app(database_path=db_path, storage_root=storage_root, sync_pipelines=True)
    return TestClient(app)


@pytest.fixture()
def pipeline_client(tmp_path: Path) -> TestClient:
    db_path = tmp_path / "pipeline.sqlite3"
    storage_root = tmp_path / "storage"
    storage_root.mkdir(parents=True, exist_ok=True)
    from app.db.session import Database

    database = Database(db_path)
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
        database_path=db_path,
        storage_root=storage_root,
        sync_pipelines=True,
        pipeline_runner=runner,
    )
    return TestClient(app)


@pytest.fixture()
def mixed_pipeline_client(tmp_path: Path) -> TestClient:
    db_path = tmp_path / "mixed.sqlite3"
    storage_root = tmp_path / "storage"
    storage_root.mkdir(parents=True, exist_ok=True)
    from app.db.session import Database

    database = Database(db_path)
    task_events = TaskEventService(database)
    project_store = ProjectStore(database)
    runner = PipelineRunner(
        database=database,
        storage_root=storage_root,
        task_events=task_events,
        project_store=project_store,
        sync=True,
        pipeline=MixedResultPipeline(),
    )
    app = create_app(
        database_path=db_path,
        storage_root=storage_root,
        sync_pipelines=True,
        pipeline_runner=runner,
    )
    return TestClient(app)


def _create_project(client: TestClient) -> str:
    response = client.post("/api/projects", json={"name": "Sample Selection Test"})
    assert response.status_code == 201
    return response.json()["id"]


def _sample_structure(project_id: str, sample_id: str, *, marker: str) -> dict:
    return {
        "id": f"video-structure-{marker}",
        "projectId": project_id,
        "sourceVideoId": sample_id,
        "version": "p0-v1",
        "metadata": {"durationSec": 30.0},
        "narrative": {
            "summary": marker,
            "segments": [
                {
                    "id": "seg-hook",
                    "role": "hook",
                    "startSec": 0.0,
                    "endSec": 3.0,
                    "scriptSummary": marker,
                    "visualSummary": marker,
                    "intent": "hook",
                }
            ],
        },
        "rhythm": {
            "totalDurationSec": 30.0,
            "shotCount": 4,
            "avgShotDurationSec": 7.5,
            "tempo": "fast",
            "beatPoints": [],
            "shotBoundaries": [],
        },
        "packaging": {
            "titleCards": [],
            "stickers": [],
            "transitions": [],
            "visualDensity": "medium",
        },
        "slots": [
            {
                "id": "slot-hook",
                "segmentId": "seg-hook",
                "role": "hook",
                "startSec": 0.0,
                "endSec": 3.0,
                "requiredAssetType": "video",
                "visualIntent": marker,
                "scriptIntent": marker,
                "importance": "required",
                "constraints": {},
            }
        ],
        "evidence": [],
        "confidence": 0.8,
    }


def test_upload_batch_creates_samples(client: TestClient, tmp_path: Path) -> None:
    project_id = _create_project(client)
    files = [
        ("files", ("a.mp4", b"fake-video-a", "video/mp4")),
        ("files", ("b.mp4", b"fake-video-b", "video/mp4")),
    ]
    response = client.post(f"/api/projects/{project_id}/samples/upload-batch", files=files)
    assert response.status_code == 201
    payload = response.json()
    assert payload["batchId"]
    assert len(payload["samples"]) == 2

    batches = client.get(f"/api/projects/{project_id}/upload-batches")
    assert batches.status_code == 200
    assert len(batches.json()["batches"]) == 1
    assert len(batches.json()["batches"][0]["sampleIds"]) == 2


def test_sample_selection_crud(client: TestClient, tmp_path: Path) -> None:
    project_id = _create_project(client)
    store = ProjectStore(client.app.state.db)  # type: ignore[attr-defined]

    sample_a = store.create_sample(
        project_id=project_id,
        source_kind="local",
        status="analyzed",
        video_uri=str(tmp_path / "a.mp4"),
    )
    sample_b = store.create_sample(
        project_id=project_id,
        source_kind="local",
        status="analyzed",
        video_uri=str(tmp_path / "b.mp4"),
    )
    store.update_sample(
        sample_a["id"],
        structure=_sample_structure(project_id, sample_a["id"], marker="a"),
    )
    store.update_sample(
        sample_b["id"],
        structure=_sample_structure(project_id, sample_b["id"], marker="b"),
    )

    get_resp = client.get(f"/api/projects/{project_id}/samples/selection")
    assert get_resp.status_code == 200
    assert get_resp.json()["selection"]["primarySampleId"]

    put_resp = client.put(
        f"/api/projects/{project_id}/samples/selection",
        json={
            "primarySampleId": sample_b["id"],
            "referenceSampleIds": [sample_a["id"]],
        },
    )
    assert put_resp.status_code == 200
    assert put_resp.json()["selection"]["primarySampleId"] == sample_b["id"]

    reset_resp = client.post(f"/api/projects/{project_id}/samples/selection/reset")
    assert reset_resp.status_code == 200


def test_generation_plan_creates_run(client: TestClient, tmp_path: Path) -> None:
    project_id = _create_project(client)
    store = ProjectStore(client.app.state.db)  # type: ignore[attr-defined]
    sample = store.create_sample(
        project_id=project_id,
        source_kind="local",
        status="analyzed",
        video_uri=str(tmp_path / "a.mp4"),
    )
    store.update_sample(
        sample["id"],
        structure=_sample_structure(project_id, sample["id"], marker="primary"),
    )
    client.put(
        f"/api/projects/{project_id}/samples/selection",
        json={"primarySampleId": sample["id"], "referenceSampleIds": []},
    )

    response = client.post(
        f"/api/projects/{project_id}/generation-plan",
        json={"variants": ["high_click"]},
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["generationRunId"]
    assert len(payload["generations"]) == 1

    runs = client.get(f"/api/projects/{project_id}/generation-runs")
    assert runs.status_code == 200
    assert runs.json()["runs"][0]["id"] == payload["generationRunId"]


def test_upload_batch_starts_in_uploading_status(client: TestClient) -> None:
    project_id = _create_project(client)
    files = [
        ("files", ("a.mp4", b"fake-video-a", "video/mp4")),
    ]
    response = client.post(f"/api/projects/{project_id}/samples/upload-batch", files=files)
    assert response.status_code == 201

    batches = client.get(f"/api/projects/{project_id}/upload-batches")
    assert batches.status_code == 200
    assert batches.json()["batches"][0]["status"] == "uploading"


def test_refresh_batch_status_partial_failed(client: TestClient) -> None:
    batch_store = UploadBatchStore(client.app.state.db)  # type: ignore[attr-defined]
    batch = batch_store.create_batch(project_id="project-1", status="uploading")
    batch_store.add_sample_to_batch(batch["id"], "sample-a")
    batch_store.add_sample_to_batch(batch["id"], "sample-b")

    updated = batch_store.refresh_batch_status(
        batch["id"],
        {"sample-a": "analyzed", "sample-b": "failed"},
    )
    assert updated["status"] == "partial_failed"


def test_analyze_batch_completes_upload_batch(
    pipeline_client: TestClient,
    tmp_path: Path,
) -> None:
    project_id = _create_project(pipeline_client)
    video = tmp_path / "sample.mp4"
    video.write_bytes(b"fake")
    files = [("files", ("a.mp4", video.read_bytes(), "video/mp4"))]
    uploaded = pipeline_client.post(
        f"/api/projects/{project_id}/samples/upload-batch",
        files=files,
    )
    batch_id = uploaded.json()["batchId"]

    analyzed = pipeline_client.post(
        f"/api/projects/{project_id}/samples/analyze-batch",
        json={"uploadBatchId": batch_id},
    )
    assert analyzed.status_code == 200
    assert len(analyzed.json()["tasks"]) == 1

    batches = pipeline_client.get(f"/api/projects/{project_id}/upload-batches")
    assert batches.json()["batches"][0]["status"] == "complete"


def test_generation_run_partial_failed_when_one_variant_fails(
    mixed_pipeline_client: TestClient,
    tmp_path: Path,
) -> None:
    project_id = _create_project(mixed_pipeline_client)
    store = ProjectStore(mixed_pipeline_client.app.state.db)  # type: ignore[attr-defined]
    sample = store.create_sample(
        project_id=project_id,
        source_kind="local",
        status="analyzed",
        video_uri=str(tmp_path / "a.mp4"),
    )
    store.update_sample(
        sample["id"],
        structure=_sample_structure(project_id, sample["id"], marker="primary"),
    )
    mixed_pipeline_client.put(
        f"/api/projects/{project_id}/samples/selection",
        json={"primarySampleId": sample["id"], "referenceSampleIds": []},
    )

    created = mixed_pipeline_client.post(f"/api/projects/{project_id}/generation-plan")
    assert created.status_code == 201
    run_id = created.json()["generationRunId"]

    run = mixed_pipeline_client.get(f"/api/projects/{project_id}/generation-runs/{run_id}")
    assert run.status_code == 200
    assert run.json()["run"]["status"] == "partial_failed"
    assert run.json()["run"]["provenanceId"] is None
