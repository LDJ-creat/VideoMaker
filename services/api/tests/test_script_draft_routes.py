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
) -> None:
    generation_root = storage_root / "projects" / project_id / "generations" / generation_id
    generation_root.mkdir(parents=True, exist_ok=True)
    draft = {
        "generationId": generation_id,
        "projectId": project_id,
        "variant": "high_click",
        "masterNarration": "开场钩子口播",
        "masterNarrationStatus": "draft",
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
        "storyboardStatus": "draft",
        "durationTargetSec": 45,
        "generationStrategy": "long_form_composed",
    }
    (generation_root / "script-draft.json").write_text(
        json.dumps(draft, ensure_ascii=False),
        encoding="utf-8",
    )


def test_get_and_update_script_draft(script_client) -> None:
    client, storage_root, project_store, task_events, _ = script_client
    project = client.post("/api/projects", json={"name": "ScriptDraft"}).json()
    task = task_events.create_task(
        project_id=project["id"],
        stage="awaiting_master_review",
        message="paused",
    )
    created = project_store.create_generation(
        project_id=project["id"],
        task_id=task["taskId"],
        status="awaiting_review",
        variant="high_click",
    )
    generation_id = created["id"]
    _write_script_draft(storage_root, project_id=project["id"], generation_id=generation_id)

    get_response = client.get(f"/api/generations/{generation_id}/script-draft")
    assert get_response.status_code == 200
    assert get_response.json()["draft"]["masterNarration"] == "开场钩子口播"

    put_response = client.put(
        f"/api/generations/{generation_id}/script-draft",
        json={"masterNarration": "更新后的总脚本"},
    )
    assert put_response.status_code == 200
    assert put_response.json()["draft"]["masterNarration"] == "更新后的总脚本"


def test_put_script_draft_rejects_invalid_payload(script_client) -> None:
    client, storage_root, project_store, task_events, _ = script_client
    project = client.post("/api/projects", json={"name": "InvalidDraft"}).json()
    task = task_events.create_task(
        project_id=project["id"],
        stage="awaiting_master_review",
        message="paused",
    )
    created = project_store.create_generation(
        project_id=project["id"],
        task_id=task["taskId"],
        status="awaiting_review",
        variant="high_click",
    )
    generation_id = created["id"]
    _write_script_draft(storage_root, project_id=project["id"], generation_id=generation_id)

    response = client.put(
        f"/api/generations/{generation_id}/script-draft",
        json={"masterNarration": "ok", "storyboard": [{"id": "bad"}]},
    )
    assert response.status_code == 400


def test_approve_master_triggers_retry(
    script_client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, storage_root, project_store, task_events, runner = script_client
    project = client.post("/api/projects", json={"name": "ApproveMaster"}).json()
    task = task_events.create_task(
        project_id=project["id"],
        stage="awaiting_master_review",
        message="paused",
    )
    created = project_store.create_generation(
        project_id=project["id"],
        task_id=task["taskId"],
        status="awaiting_review",
        variant="high_click",
    )
    generation_id = created["id"]
    _write_script_draft(storage_root, project_id=project["id"], generation_id=generation_id)

    called: list[str] = []

    def _fake_retry(self, task_id: str) -> None:  # noqa: ANN001
        called.append(task_id)

    monkeypatch.setattr(type(runner), "retry_task", _fake_retry)

    response = client.post(f"/api/generations/{generation_id}/approve-master")
    assert response.status_code == 202
    body = response.json()
    assert body["draft"]["masterNarrationStatus"] == "approved"
    assert called == [task["taskId"]]
