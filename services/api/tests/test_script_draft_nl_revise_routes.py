from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.test_p0_flow_routes import FakeDemoPipeline


@pytest.fixture()
def script_client(app_paths):
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
    return TestClient(app), storage_root, project_store, task_events, runner


def _write_script_draft(
    storage_root: Path,
    *,
    project_id: str,
    generation_id: str,
    master_status: str = "draft",
    storyboard_status: str = "draft",
) -> None:
    generation_root = storage_root / "projects" / project_id / "generations" / generation_id
    generation_root.mkdir(parents=True, exist_ok=True)
    draft = {
        "generationId": generation_id,
        "projectId": project_id,
        "variant": "high_click",
        "masterNarration": "开场钩子口播",
        "masterNarrationStatus": master_status,
        "storyboard": [
            {
                "id": "scene-1",
                "slotId": "slot-1",
                "startSec": 0,
                "endSec": 5,
                "visual": "产品特写",
                "script": "口播一",
                "source": "text_completion",
            }
        ],
        "storyboardStatus": storyboard_status,
        "durationTargetSec": 45,
        "generationStrategy": "short_form_direct",
    }
    (generation_root / "script-draft.json").write_text(
        json.dumps(draft, ensure_ascii=False),
        encoding="utf-8",
    )


def test_nl_revise_master_success(script_client) -> None:
    client, storage_root, project_store, task_events, _ = script_client
    project = client.post("/api/projects", json={"name": "NlRevise"}).json()
    project_id = project["id"]
    task = task_events.create_task(
        project_id,
        stage="awaiting_master_review",
        message="review master",
        status="awaiting_review",
    )
    generation = project_store.create_generation(
        project_id=project_id,
        task_id=task["taskId"],
        status="awaiting_review",
        variant="high_click",
    )
    generation_id = generation["id"]
    _write_script_draft(storage_root, project_id=project_id, generation_id=generation_id)

    response = client.post(
        f"/api/generations/{generation_id}/script-draft/nl-revise",
        json={"scope": "master", "instruction": "开头更抓人"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["revisionId"] == "rev-fake-1"
    assert body["summary"] == "fake revise master"
    assert "revised-开头更抓人" in body["draft"]["masterNarration"]


def test_nl_revise_rejects_wrong_stage(script_client) -> None:
    client, storage_root, project_store, task_events, _ = script_client
    project = client.post("/api/projects", json={"name": "NlReviseGate"}).json()
    project_id = project["id"]
    task = task_events.create_task(
        project_id,
        stage="awaiting_storyboard_review",
        message="review storyboard",
        status="awaiting_review",
    )
    generation = project_store.create_generation(
        project_id=project_id,
        task_id=task["taskId"],
        status="awaiting_review",
        variant="high_click",
    )
    generation_id = generation["id"]
    _write_script_draft(storage_root, project_id=project_id, generation_id=generation_id)

    response = client.post(
        f"/api/generations/{generation_id}/script-draft/nl-revise",
        json={"scope": "master", "instruction": "开头更抓人"},
    )
    assert response.status_code == 400
    assert "awaiting_master_review" in response.json()["detail"]


def test_nl_revise_storyboard_success(script_client) -> None:
    client, storage_root, project_store, task_events, _ = script_client
    project = client.post("/api/projects", json={"name": "NlReviseStoryboard"}).json()
    project_id = project["id"]
    task = task_events.create_task(
        project_id,
        stage="awaiting_storyboard_review",
        message="review storyboard",
        status="awaiting_review",
    )
    generation = project_store.create_generation(
        project_id=project_id,
        task_id=task["taskId"],
        status="awaiting_review",
        variant="high_click",
    )
    generation_id = generation["id"]
    _write_script_draft(
        storage_root,
        project_id=project_id,
        generation_id=generation_id,
        master_status="approved",
    )

    response = client.post(
        f"/api/generations/{generation_id}/script-draft/nl-revise",
        json={"scope": "storyboard", "instruction": "第二镜户外场景"},
    )
    assert response.status_code == 200
    assert response.json()["summary"] == "fake revise storyboard"
