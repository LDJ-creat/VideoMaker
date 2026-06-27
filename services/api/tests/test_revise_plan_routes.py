from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.test_revise_generation import (
    ReviseFakeDemoPipeline,
    _create_source_generation,
    _prepare_project_with_structure,
    _sample_plan,
    _seed_source_generation,
)


@pytest.fixture()
def revise_client(app_paths):
    from app.db.session import Database
    from app.main import create_app
    from app.services.pipeline_runner import PipelineRunner
    from app.services.project_store import ProjectStore
    from app.services.task_events import TaskEventService

    database_path = app_paths["database_path"]
    storage_root = app_paths["storage_root"]
    database = Database(database_path)
    task_events = TaskEventService(database)
    project_store = ProjectStore(database)
    runner = PipelineRunner(
        database=database,
        storage_root=storage_root,
        task_events=task_events,
        project_store=project_store,
        sync=True,
        pipeline=ReviseFakeDemoPipeline(),
    )
    app = create_app(
        database_path=database_path,
        storage_root=storage_root,
        sync_pipelines=True,
        pipeline_runner=runner,
    )
    return TestClient(app)


def test_plan_revise_returns_draft_plan(
    revise_client: TestClient,
    app_paths,
    tmp_path: Path,
) -> None:
    project = _prepare_project_with_structure(revise_client, tmp_path)
    generation_id = _create_source_generation(app_paths, project["id"])

    response = revise_client.post(
        f"/api/generations/{generation_id}/revise/plan",
        json={"instruction": "字幕少一点"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["plan"]["status"] == "draft"
    assert body["plan"]["executionMode"] == "in_place"
    assert body["sessionId"]

    session_path = (
        app_paths["storage_root"]
        / "projects"
        / project["id"]
        / "generations"
        / generation_id
        / "revise-session.json"
    )
    assert session_path.is_file()


def test_plan_revise_rejects_unparseable_instruction(
    revise_client: TestClient,
    app_paths,
    tmp_path: Path,
) -> None:
    project = _prepare_project_with_structure(revise_client, tmp_path)
    generation_id = _create_source_generation(app_paths, project["id"])

    response = revise_client.post(
        f"/api/generations/{generation_id}/revise/plan",
        json={"instruction": "把背景音乐换成更轻快的"},
    )
    assert response.status_code == 400
    assert "Could not parse any edit intents from instruction" in response.json()["detail"]


def test_execute_in_place_revise_patch(
    revise_client: TestClient,
    app_paths,
    tmp_path: Path,
) -> None:
    project = _prepare_project_with_structure(revise_client, tmp_path)
    generation_id = _create_source_generation(app_paths, project["id"])

    plan_response = revise_client.post(
        f"/api/generations/{generation_id}/revise/plan",
        json={"instruction": "字幕少一点"},
    ).json()
    plan_id = plan_response["plan"]["planId"]

    execute = revise_client.post(
        f"/api/generations/{generation_id}/revise/execute",
        json={"planId": plan_id},
    )
    assert execute.status_code == 202
    body = execute.json()
    assert body["executionMode"] == "in_place"
    assert body["generationId"] == generation_id
    assert body["taskId"]


def test_get_revise_session(
    revise_client: TestClient,
    app_paths,
    tmp_path: Path,
) -> None:
    project = _prepare_project_with_structure(revise_client, tmp_path)
    generation_id = _create_source_generation(app_paths, project["id"])
    revise_client.post(
        f"/api/generations/{generation_id}/revise/plan",
        json={"instruction": "字幕少一点"},
    )
    session = revise_client.get(f"/api/generations/{generation_id}/revise/session")
    assert session.status_code == 200
    body = session.json()
    assert body["session"] is not None
    assert len(body["session"]["turns"]) == 1


def test_execute_in_place_marks_plan_executing(
    revise_client: TestClient,
    app_paths,
    tmp_path: Path,
) -> None:
    project = _prepare_project_with_structure(revise_client, tmp_path)
    generation_id = _create_source_generation(app_paths, project["id"])
    plan_id = revise_client.post(
        f"/api/generations/{generation_id}/revise/plan",
        json={"instruction": "字幕少一点"},
    ).json()["plan"]["planId"]

    execute = revise_client.post(
        f"/api/generations/{generation_id}/revise/execute",
        json={"planId": plan_id},
    )
    assert execute.status_code == 202
    body = execute.json()
    assert body["plan"]["status"] == "executing"

    from app.services.revise_plan_service import load_plan

    stored = load_plan(
        app_paths["storage_root"],
        project["id"],
        generation_id,
        plan_id,
    )
    assert stored is not None
    assert stored["status"] in {"executing", "executed"}


def test_cancel_revise_plan(
    revise_client: TestClient,
    app_paths,
    tmp_path: Path,
) -> None:
    project = _prepare_project_with_structure(revise_client, tmp_path)
    generation_id = _create_source_generation(app_paths, project["id"])
    plan_id = revise_client.post(
        f"/api/generations/{generation_id}/revise/plan",
        json={"instruction": "字幕少一点"},
    ).json()["plan"]["planId"]

    cancel = revise_client.post(
        f"/api/generations/{generation_id}/revise/cancel",
        json={"planId": plan_id},
    )
    assert cancel.status_code == 200
    assert plan_id in cancel.json()["planIds"]

    session = revise_client.get(f"/api/generations/{generation_id}/revise/session").json()
    assert session["pendingPlan"] is None


def test_execute_fork_revise_plan(
    revise_client: TestClient,
    app_paths,
    tmp_path: Path,
) -> None:
    project = _prepare_project_with_structure(revise_client, tmp_path)
    generation_id = _create_source_generation(app_paths, project["id"])
    plan_id = revise_client.post(
        f"/api/generations/{generation_id}/revise/plan",
        json={"instruction": "开头更抓人一些"},
    ).json()["plan"]["planId"]

    execute = revise_client.post(
        f"/api/generations/{generation_id}/revise/execute",
        json={"planId": plan_id},
    )
    assert execute.status_code == 202
    body = execute.json()
    assert body["executionMode"] == "fork"
    assert body["generationId"] != generation_id
    assert body["plan"]["status"] == "executing"


def test_execute_rejects_invalid_plan_id(
    revise_client: TestClient,
    app_paths,
    tmp_path: Path,
) -> None:
    project = _prepare_project_with_structure(revise_client, tmp_path)
    generation_id = _create_source_generation(app_paths, project["id"])

    response = revise_client.post(
        f"/api/generations/{generation_id}/revise/execute",
        json={"planId": "../escape"},
    )
    assert response.status_code == 400


def test_execute_rejects_non_draft_plan(
    revise_client: TestClient,
    app_paths,
    tmp_path: Path,
) -> None:
    project = _prepare_project_with_structure(revise_client, tmp_path)
    generation_id = _create_source_generation(app_paths, project["id"])
    plan_id = revise_client.post(
        f"/api/generations/{generation_id}/revise/plan",
        json={"instruction": "字幕少一点"},
    ).json()["plan"]["planId"]

    first = revise_client.post(
        f"/api/generations/{generation_id}/revise/execute",
        json={"planId": plan_id},
    )
    assert first.status_code == 202

    second = revise_client.post(
        f"/api/generations/{generation_id}/revise/execute",
        json={"planId": plan_id},
    )
    assert second.status_code == 400


class PatchFailDemoPipeline(ReviseFakeDemoPipeline):
    def execute_revise_patch(
        self,
        *,
        project_id: str,
        task_id: str,
        generation_id: str,
        plan: dict,
        emit: Any,
    ) -> dict[str, Any]:
        _ = (project_id, generation_id, plan)
        emit(
            status="failed",
            stage="applying_revise_patch",
            progress=0,
            message="patch failed",
            error={"code": "revise_patch_failed", "message": "boom", "retryable": True},
        )
        return {"ok": False, "error": "boom"}


@pytest.fixture()
def patch_fail_client(app_paths):
    from app.db.session import Database
    from app.main import create_app
    from app.services.pipeline_runner import PipelineRunner
    from app.services.project_store import ProjectStore
    from app.services.task_events import TaskEventService

    database_path = app_paths["database_path"]
    storage_root = app_paths["storage_root"]
    database = Database(database_path)
    task_events = TaskEventService(database)
    project_store = ProjectStore(database)
    runner = PipelineRunner(
        database=database,
        storage_root=storage_root,
        task_events=task_events,
        project_store=project_store,
        sync=True,
        pipeline=PatchFailDemoPipeline(),
    )
    app = create_app(
        database_path=database_path,
        storage_root=storage_root,
        sync_pipelines=True,
        pipeline_runner=runner,
    )
    return TestClient(app), runner


def test_in_place_patch_failure_keeps_generation_reviseable(
    patch_fail_client,
    app_paths,
    tmp_path: Path,
) -> None:
    client, runner = patch_fail_client
    project = _prepare_project_with_structure(client, tmp_path)
    generation_id = _create_source_generation(app_paths, project["id"])
    plan_id = client.post(
        f"/api/generations/{generation_id}/revise/plan",
        json={"instruction": "字幕少一点"},
    ).json()["plan"]["planId"]

    execute = client.post(
        f"/api/generations/{generation_id}/revise/execute",
        json={"planId": plan_id},
    )
    assert execute.status_code == 202
    task_id = execute.json()["taskId"]

    from app.db.session import Database
    from app.services.project_store import ProjectStore

    store = ProjectStore(Database(app_paths["database_path"]))
    source = store.get_generation(generation_id)
    assert source is not None
    assert source["status"] == "succeeded"

    from app.services.revise_plan_service import load_plan, load_revise_patch_context

    plan = load_plan(app_paths["storage_root"], project["id"], generation_id, plan_id)
    assert plan is not None
    assert plan["status"] == "approved"
    assert load_revise_patch_context(
        app_paths["storage_root"],
        project["id"],
        generation_id,
    ) is not None

    runner.retry_task(task_id)
    source_after_retry = store.get_generation(generation_id)
    assert source_after_retry is not None
    assert source_after_retry["status"] == "succeeded"

    replan = client.post(
        f"/api/generations/{generation_id}/revise/plan",
        json={"instruction": "字幕少一点"},
    )
    assert replan.status_code == 200


def _structured_payload(
    *,
    mode: str = "edit",
    scene_id: str = "scene-1",
    slot_id: str = "slot-1",
    instruction: str = "字幕居中，样式保持不变",
) -> dict[str, Any]:
    return {
        "structured": {
            "sceneId": scene_id,
            "slotId": slot_id,
            "mode": mode,
            "instruction": instruction,
        }
    }


def test_plan_revise_structured_edit_mode(
    revise_client: TestClient,
    app_paths,
    tmp_path: Path,
) -> None:
    project = _prepare_project_with_structure(revise_client, tmp_path)
    generation_id = _create_source_generation(app_paths, project["id"])

    response = revise_client.post(
        f"/api/generations/{generation_id}/revise/plan",
        json=_structured_payload(mode="edit"),
    )
    assert response.status_code == 200
    plan = response.json()["plan"]
    assert plan["executionMode"] == "fork"
    assert plan.get("planSource") == "scene_structured"
    assert plan["intents"][0]["executionTool"] == "material_regen"
    assert plan["intents"][0]["params"]["materialEditMode"] == "edit"
    assert plan["intents"][0]["params"]["editInstruction"] == "字幕居中，样式保持不变"
    assert plan["affectedSlotIds"] == ["slot-1"]


def test_plan_revise_structured_full_mode(
    revise_client: TestClient,
    app_paths,
    tmp_path: Path,
) -> None:
    project = _prepare_project_with_structure(revise_client, tmp_path)
    generation_id = _create_source_generation(app_paths, project["id"])

    response = revise_client.post(
        f"/api/generations/{generation_id}/revise/plan",
        json=_structured_payload(mode="full", instruction="改成赛博朋克风格"),
    )
    assert response.status_code == 200
    plan = response.json()["plan"]
    assert plan["executionMode"] == "fork"
    assert plan["intents"][0]["params"]["materialEditMode"] == "full"


def test_plan_revise_structured_missing_instruction(
    revise_client: TestClient,
    app_paths,
    tmp_path: Path,
) -> None:
    project = _prepare_project_with_structure(revise_client, tmp_path)
    generation_id = _create_source_generation(app_paths, project["id"])

    response = revise_client.post(
        f"/api/generations/{generation_id}/revise/plan",
        json={
            "structured": {
                "sceneId": "scene-1",
                "slotId": "slot-1",
                "mode": "edit",
                "instruction": "",
            }
        },
    )
    assert response.status_code == 422


def test_plan_revise_rejects_missing_plan_input(
    revise_client: TestClient,
    app_paths,
    tmp_path: Path,
) -> None:
    project = _prepare_project_with_structure(revise_client, tmp_path)
    generation_id = _create_source_generation(app_paths, project["id"])

    response = revise_client.post(
        f"/api/generations/{generation_id}/revise/plan",
        json={"newSession": False},
    )
    assert response.status_code == 422


def test_plan_revise_rejects_both_instruction_and_structured(
    revise_client: TestClient,
    app_paths,
    tmp_path: Path,
) -> None:
    project = _prepare_project_with_structure(revise_client, tmp_path)
    generation_id = _create_source_generation(app_paths, project["id"])

    response = revise_client.post(
        f"/api/generations/{generation_id}/revise/plan",
        json={
            "instruction": "字幕少一点",
            **_structured_payload(),
        },
    )
    assert response.status_code == 422


def test_plan_revise_structured_rejects_invalid_scene(
    revise_client: TestClient,
    app_paths,
    tmp_path: Path,
) -> None:
    project = _prepare_project_with_structure(revise_client, tmp_path)
    generation_id = _create_source_generation(app_paths, project["id"])

    response = revise_client.post(
        f"/api/generations/{generation_id}/revise/plan",
        json=_structured_payload(scene_id="missing-scene"),
    )
    assert response.status_code == 400
    assert "sceneId not found" in response.json()["detail"]
