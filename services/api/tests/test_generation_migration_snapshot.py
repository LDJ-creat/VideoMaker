from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


from tests.test_p0_flow_routes import FakeDemoPipeline


@pytest.fixture()
def migration_client(app_paths):
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
    return TestClient(app), storage_root, project_store, task_events


def _write_migration_artifacts(
    storage_root: Path,
    *,
    project_id: str,
    generation_id: str,
) -> None:
    generation_root = (
        storage_root / "projects" / project_id / "generations" / generation_id
    )
    generation_root.mkdir(parents=True, exist_ok=True)
    (generation_root / "slot-matches.json").write_text(
        json.dumps(
            {
                "slotMatches": [
                    {
                        "slotId": "slot-1",
                        "matchScore": 0.8,
                        "assetId": "asset-1",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (generation_root / "gap-report.json").write_text(
        json.dumps(
            {
                "weakSlots": [],
                "missingSlots": [{"slotId": "slot-2", "reason": "no asset"}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (generation_root / "generation-plan.json").write_text(
        json.dumps(
            {
                "completionActions": [
                    {
                        "id": "action-slot-2",
                        "slotId": "slot-2",
                        "provider": "hyperframes_material",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (generation_root / "material-state.json").write_text(
        json.dumps(
            {"completedActionIds": ["action-slot-2"]},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_migration_snapshot_happy_path(migration_client) -> None:
    client, storage_root, project_store, task_events = migration_client
    project = client.post("/api/projects", json={"name": "MigrationSnapshot"}).json()
    task = task_events.create_task(
        project_id=project["id"],
        stage="mapping_slots",
        message="running",
    )
    created = project_store.create_generation(
        project_id=project["id"],
        task_id=task["taskId"],
        status="running",
        variant="high_click",
    )
    generation_id = created["id"]
    _write_migration_artifacts(
        storage_root,
        project_id=project["id"],
        generation_id=generation_id,
    )

    response = client.get(f"/api/generations/{generation_id}/migration-snapshot")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["slotMatches"]) == 1
    assert payload["slotMatches"][0]["slotId"] == "slot-1"
    assert payload["gapReport"]["missingSlots"][0]["slotId"] == "slot-2"
    assert payload["completionActions"][0]["provider"] == "hyperframes_material"
    assert payload["materialState"]["completedActionIds"] == ["action-slot-2"]


def test_migration_snapshot_generation_not_found(migration_client) -> None:
    client, *_ = migration_client
    response = client.get("/api/generations/missing-generation/migration-snapshot")
    assert response.status_code == 404
