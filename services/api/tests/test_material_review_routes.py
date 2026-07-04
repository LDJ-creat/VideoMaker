from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.test_p0_flow_routes import FakeDemoPipeline
from tests.test_revise_generation import _create_source_generation, _prepare_project_with_structure


@pytest.fixture()
def material_review_client(app_paths, tmp_path):
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
        pipeline=FakeDemoPipeline(),
    )
    app = create_app(
        database_path=database_path,
        storage_root=storage_root,
        sync_pipelines=True,
        pipeline_runner=runner,
    )
    return TestClient(app), app_paths, tmp_path


def _write_material_review_state(
    storage_root: Path,
    *,
    project_id: str,
    generation_id: str,
    awaiting_gate: str | None = "material_review",
    slots: dict[str, dict[str, str]] | None = None,
) -> None:
    generation_root = storage_root / "projects" / project_id / "generations" / generation_id
    generation_root.mkdir(parents=True, exist_ok=True)
    state = {
        "generationId": generation_id,
        "projectId": project_id,
        "variant": "high_click",
        "status": "draft",
        "slots": slots
        or {
            "hook": {"status": "agent_passed"},
        },
    }
    (generation_root / "material-review-state.json").write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    checkpoint = {"awaitingGate": awaiting_gate}
    (generation_root / "checkpoint.json").write_text(
        json.dumps(checkpoint, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _write_generation_plan(
    storage_root: Path,
    *,
    project_id: str,
    generation_id: str,
    completion_actions: list[dict[str, object]] | None = None,
) -> None:
    generation_root = storage_root / "projects" / project_id / "generations" / generation_id
    generation_root.mkdir(parents=True, exist_ok=True)
    plan = {
        "id": generation_id,
        "projectId": project_id,
        "variant": "high_click",
        "completionActions": completion_actions
        or [
            {
                "id": "action-hook",
                "slotId": "hook",
                "provider": "hyperframes_material",
            }
        ],
    }
    (generation_root / "generation-plan.json").write_text(
        json.dumps(plan, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _set_task_awaiting_material_review(database_path: Path, task_id: str) -> None:
    from app.db.session import Database
    from app.services.task_events import TaskEventService

    task_events = TaskEventService(Database(database_path))
    task_events.update_task(
        task_id,
        status="awaiting_review",
        stage="awaiting_material_review",
        progress=72,
        message="Review slot material previews before final assembly",
    )


def test_resolve_generation_by_task(material_review_client) -> None:
    client, app_paths, tmp_path = material_review_client
    project = _prepare_project_with_structure(client, tmp_path)
    project_id = str(project["id"])
    generation_id = _create_source_generation(app_paths, project_id)

    response = client.get("/api/generations/resolve/by-task/task-source")
    assert response.status_code == 200
    assert response.json()["generationId"] == generation_id
    assert response.json()["projectId"] == project_id


def test_get_material_review(material_review_client) -> None:
    client, app_paths, tmp_path = material_review_client
    storage_root = app_paths["storage_root"]
    project = _prepare_project_with_structure(client, tmp_path)
    project_id = str(project["id"])
    generation_id = _create_source_generation(app_paths, project_id)
    _write_material_review_state(storage_root, project_id=project_id, generation_id=generation_id)

    response = client.get(f"/api/generations/{generation_id}/material-review")
    assert response.status_code == 200
    payload = response.json()
    assert payload["state"]["generationId"] == generation_id
    assert payload["state"]["slots"]["hook"]["status"] == "agent_passed"


def test_get_material_review_includes_revise_context(material_review_client) -> None:
    client, app_paths, tmp_path = material_review_client
    storage_root = app_paths["storage_root"]
    project = _prepare_project_with_structure(client, tmp_path)
    project_id = str(project["id"])
    generation_id = _create_source_generation(app_paths, project_id)
    _write_material_review_state(storage_root, project_id=project_id, generation_id=generation_id)
    generation_root = storage_root / "projects" / project_id / "generations" / generation_id
    (generation_root / "revise-context.json").write_text(
        json.dumps(
            {
                "sourceGenerationId": "gen-source",
                "materialReviewScope": "scoped",
                "materialReviewSlotIds": ["hook"],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    response = client.get(f"/api/generations/{generation_id}/material-review")
    assert response.status_code == 200
    payload = response.json()
    assert payload["reviseContext"]["scope"] == "scoped"
    assert payload["reviseContext"]["sourceGenerationId"] == "gen-source"
    assert payload["reviseContext"]["affectedSlotIds"] == ["hook"]


def test_approve_material(material_review_client, monkeypatch: pytest.MonkeyPatch) -> None:
    client, app_paths, tmp_path = material_review_client
    storage_root = app_paths["storage_root"]
    from app.db.session import Database
    from app.services.project_store import ProjectStore
    from app.services.task_events import TaskEventService

    database = Database(app_paths["database_path"])
    project_store = ProjectStore(database)
    task_events = TaskEventService(database)
    project = _prepare_project_with_structure(client, tmp_path)
    project_id = str(project["id"])
    task = task_events.create_task(
        project_id=project_id,
        stage="awaiting_material_review",
        message="paused",
    )
    created = project_store.create_generation(
        project_id=project_id,
        task_id=task["taskId"],
        status="awaiting_review",
        variant="high_click",
    )
    generation_id = created["id"]
    _write_material_review_state(storage_root, project_id=project_id, generation_id=generation_id)
    _write_generation_plan(storage_root, project_id=project_id, generation_id=generation_id)
    generated_root = (
        storage_root / "projects" / project_id / "generations" / generation_id / "generated"
    )
    generated_root.mkdir(parents=True, exist_ok=True)
    (generated_root / "action-hook.mp4").write_bytes(b"\x00" * 120_000)
    _set_task_awaiting_material_review(app_paths["database_path"], task["taskId"])

    called: list[str] = []

    def _fake_retry(_self, task_id: str) -> None:  # noqa: ANN001
        called.append(task_id)

    from app.services.pipeline_runner import PipelineRunner

    monkeypatch.setattr(PipelineRunner, "retry_task", _fake_retry)

    response = client.post(f"/api/generations/{generation_id}/approve-material")
    assert response.status_code == 202
    payload = response.json()
    assert payload["state"]["status"] == "approved"
    assert called == [task["taskId"]]

    generation_root = storage_root / "projects" / project_id / "generations" / generation_id
    checkpoint = json.loads((generation_root / "checkpoint.json").read_text(encoding="utf-8"))
    assert checkpoint.get("awaitingGate") is None


def test_approve_material_rejects_when_gate_inactive(material_review_client) -> None:
    client, app_paths, tmp_path = material_review_client
    storage_root = app_paths["storage_root"]
    project = _prepare_project_with_structure(client, tmp_path)
    project_id = str(project["id"])
    generation_id = _create_source_generation(app_paths, project_id)
    _write_material_review_state(
        storage_root,
        project_id=project_id,
        generation_id=generation_id,
        awaiting_gate=None,
    )

    response = client.post(f"/api/generations/{generation_id}/approve-material")
    assert response.status_code == 400
    assert response.json()["detail"] == "Generation is not awaiting material review"


def test_approve_material_allows_agent_failed_override_with_artifact(
    material_review_client, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, app_paths, tmp_path = material_review_client
    storage_root = app_paths["storage_root"]
    from app.db.session import Database
    from app.services.project_store import ProjectStore
    from app.services.task_events import TaskEventService

    database = Database(app_paths["database_path"])
    project_store = ProjectStore(database)
    task_events = TaskEventService(database)
    project = _prepare_project_with_structure(client, tmp_path)
    project_id = str(project["id"])
    task = task_events.create_task(
        project_id=project_id,
        stage="awaiting_material_review",
        message="paused",
    )
    created = project_store.create_generation(
        project_id=project_id,
        task_id=task["taskId"],
        status="awaiting_review",
        variant="high_click",
    )
    generation_id = created["id"]
    _write_material_review_state(
        storage_root,
        project_id=project_id,
        generation_id=generation_id,
        slots={
            "hook": {"status": "agent_failed"},
        },
    )
    _write_generation_plan(storage_root, project_id=project_id, generation_id=generation_id)
    generated_root = (
        storage_root / "projects" / project_id / "generations" / generation_id / "generated"
    )
    generated_root.mkdir(parents=True, exist_ok=True)
    (generated_root / "action-hook.mp4").write_bytes(b"\x00" * 120_000)
    _set_task_awaiting_material_review(app_paths["database_path"], task["taskId"])

    monkeypatch.setattr(
        "app.services.pipeline_runner.PipelineRunner.retry_task",
        lambda _self, task_id: None,
    )

    response = client.post(f"/api/generations/{generation_id}/approve-material")
    assert response.status_code == 202
    payload = response.json()
    assert payload["state"]["status"] == "approved"
    assert payload["state"].get("humanOverride") is True
    assert payload["state"].get("overriddenSlotIds") == ["hook"]


def test_approve_material_rejects_agent_failed_without_artifact(material_review_client) -> None:
    client, app_paths, tmp_path = material_review_client
    storage_root = app_paths["storage_root"]
    from app.db.session import Database
    from app.services.project_store import ProjectStore
    from app.services.task_events import TaskEventService

    database = Database(app_paths["database_path"])
    project_store = ProjectStore(database)
    task_events = TaskEventService(database)
    project = _prepare_project_with_structure(client, tmp_path)
    project_id = str(project["id"])
    task = task_events.create_task(
        project_id=project_id,
        stage="awaiting_material_review",
        message="paused",
    )
    created = project_store.create_generation(
        project_id=project_id,
        task_id=task["taskId"],
        status="awaiting_review",
        variant="high_click",
    )
    generation_id = created["id"]
    _write_material_review_state(
        storage_root,
        project_id=project_id,
        generation_id=generation_id,
        slots={
            "hook": {"status": "agent_failed"},
        },
    )
    _write_generation_plan(storage_root, project_id=project_id, generation_id=generation_id)
    _set_task_awaiting_material_review(app_paths["database_path"], task["taskId"])

    response = client.post(f"/api/generations/{generation_id}/approve-material")
    assert response.status_code == 400
    assert "hook" in response.json()["detail"]


def test_approve_material_rejects_hard_gate_failed(material_review_client) -> None:
    client, app_paths, tmp_path = material_review_client
    storage_root = app_paths["storage_root"]
    from app.db.session import Database
    from app.services.project_store import ProjectStore
    from app.services.task_events import TaskEventService

    database = Database(app_paths["database_path"])
    project_store = ProjectStore(database)
    task_events = TaskEventService(database)
    project = _prepare_project_with_structure(client, tmp_path)
    project_id = str(project["id"])
    task = task_events.create_task(
        project_id=project_id,
        stage="awaiting_material_review",
        message="paused",
    )
    created = project_store.create_generation(
        project_id=project_id,
        task_id=task["taskId"],
        status="awaiting_review",
        variant="high_click",
    )
    generation_id = created["id"]
    _write_material_review_state(
        storage_root,
        project_id=project_id,
        generation_id=generation_id,
        slots={
            "hook": {"status": "hard_gate_failed", "hardGateFailed": True},
        },
    )
    _write_generation_plan(storage_root, project_id=project_id, generation_id=generation_id)
    generated_root = (
        storage_root / "projects" / project_id / "generations" / generation_id / "generated"
    )
    generated_root.mkdir(parents=True, exist_ok=True)
    (generated_root / "action-hook.mp4").write_bytes(b"\x00" * 120_000)
    _set_task_awaiting_material_review(app_paths["database_path"], task["taskId"])

    response = client.post(f"/api/generations/{generation_id}/approve-material")
    assert response.status_code == 400
    assert "hook" in response.json()["detail"]


def test_approve_material_rejects_when_task_running(material_review_client) -> None:
    client, app_paths, tmp_path = material_review_client
    storage_root = app_paths["storage_root"]
    from app.db.session import Database
    from app.services.project_store import ProjectStore
    from app.services.task_events import TaskEventService

    database = Database(app_paths["database_path"])
    project_store = ProjectStore(database)
    task_events = TaskEventService(database)
    project = _prepare_project_with_structure(client, tmp_path)
    project_id = str(project["id"])
    task = task_events.create_task(
        project_id=project_id,
        stage="generating_material",
        message="regenerating slot",
    )
    task_events.update_task(
        task["taskId"],
        status="running",
        stage="generating_material",
        progress=65,
        message="regenerating slot",
    )
    created = project_store.create_generation(
        project_id=project_id,
        task_id=task["taskId"],
        status="running",
        variant="high_click",
    )
    generation_id = created["id"]
    _write_material_review_state(storage_root, project_id=project_id, generation_id=generation_id)
    _write_generation_plan(storage_root, project_id=project_id, generation_id=generation_id)

    response = client.post(f"/api/generations/{generation_id}/approve-material")
    assert response.status_code == 400
    assert response.json()["detail"] == "Task is not awaiting material review"


def test_get_material_review_includes_stock_preview_url(material_review_client) -> None:
    client, app_paths, tmp_path = material_review_client
    storage_root = app_paths["storage_root"]
    project = _prepare_project_with_structure(client, tmp_path)
    project_id = str(project["id"])
    generation_id = _create_source_generation(app_paths, project_id)
    _write_material_review_state(
        storage_root,
        project_id=project_id,
        generation_id=generation_id,
        slots={"usage": {"status": "skipped"}},
    )
    _write_generation_plan(
        storage_root,
        project_id=project_id,
        generation_id=generation_id,
        completion_actions=[
            {
                "id": "action-usage-stock",
                "slotId": "usage",
                "provider": "stock_media_search",
            }
        ],
    )
    generated_root = (
        storage_root / "projects" / project_id / "generations" / generation_id / "generated"
    )
    generated_root.mkdir(parents=True, exist_ok=True)
    (generated_root / "usage-stock.mp4").write_bytes(b"\x00" * 120_000)

    response = client.get(f"/api/generations/{generation_id}/material-review")
    assert response.status_code == 200
    previews = response.json()["slotPreviewUrls"]
    assert "usage" in previews
    assert "/generated/usage-stock.mp4" in previews["usage"]


def test_get_material_review_preview_url_includes_cache_version(
    material_review_client,
) -> None:
    client, app_paths, tmp_path = material_review_client
    storage_root = app_paths["storage_root"]
    project = _prepare_project_with_structure(client, tmp_path)
    project_id = str(project["id"])
    generation_id = _create_source_generation(app_paths, project_id)
    generated_root = (
        storage_root / "projects" / project_id / "generations" / generation_id / "generated"
    )
    generated_root.mkdir(parents=True, exist_ok=True)
    (generated_root / "action-hook.mp4").write_bytes(b"\x00" * 120_000)
    _write_material_review_state(
        storage_root,
        project_id=project_id,
        generation_id=generation_id,
        slots={
            "hook": {
                "status": "hard_gate_failed",
                "previewArtifactRef": {
                    "id": "action-hook",
                    "type": "video",
                    "uri": str(generated_root / "action-hook.mp4"),
                    "createdAt": "2026-07-01T08:21:30.778978Z",
                },
            }
        },
    )
    _write_generation_plan(
        storage_root,
        project_id=project_id,
        generation_id=generation_id,
        completion_actions=[
            {
                "id": "action-hook",
                "slotId": "hook",
                "provider": "hyperframes_material",
            }
        ],
    )

    response = client.get(f"/api/generations/{generation_id}/material-review")
    assert response.status_code == 200
    preview = response.json()["slotPreviewUrls"]["hook"]
    assert "v=2026-07-01T08%3A21%3A30.778978Z" in preview or "v=2026-07-01T08:21:30.778978Z" in preview


def test_revise_material_slot_requires_awaiting_task(material_review_client, monkeypatch: pytest.MonkeyPatch) -> None:
    client, app_paths, tmp_path = material_review_client
    storage_root = app_paths["storage_root"]
    from app.db.session import Database
    from app.services.project_store import ProjectStore
    from app.services.task_events import TaskEventService

    database = Database(app_paths["database_path"])
    project_store = ProjectStore(database)
    task_events = TaskEventService(database)
    project = _prepare_project_with_structure(client, tmp_path)
    project_id = str(project["id"])
    task = task_events.create_task(
        project_id=project_id,
        stage="generating_material",
        message="regenerating slot",
    )
    task_events.update_task(
        task["taskId"],
        status="running",
        stage="generating_material",
        progress=65,
        message="regenerating slot",
    )
    created = project_store.create_generation(
        project_id=project_id,
        task_id=task["taskId"],
        status="running",
        variant="high_click",
    )
    generation_id = created["id"]
    _write_material_review_state(storage_root, project_id=project_id, generation_id=generation_id)

    response = client.post(
        f"/api/generations/{generation_id}/material-slots/hook/revise",
        json={"instruction": "标题更大"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Task is not awaiting material review"
