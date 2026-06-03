from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.test_p0_flow_routes import FakeDemoPipeline


class ReviseFakeDemoPipeline(FakeDemoPipeline):
    last_revise: dict[str, Any] | None = None

    def parse_edit_intent(
        self,
        *,
        project_id: str,
        task_id: str,
        instruction: str,
        source_plan: dict[str, Any],
        emit: Any,
    ) -> dict[str, Any]:
        from app.services.pipeline_runner import PipelineRunner

        intents = PipelineRunner._parse_edit_intent_rules(instruction, source_plan)  # noqa: SLF001
        return {"ok": True, "intents": intents}

    def run_revise(
        self,
        *,
        project_id: str,
        task_id: str,
        source_generation_id: str,
        generation_id: str,
        instruction: str,
        structure: dict[str, Any],
        user_brief: dict[str, Any],
        assets: list[dict[str, Any]],
        emit: Any,
        intents: list[dict[str, Any]] | None = None,
        variant: str | None = None,
        resume: bool = False,
    ) -> dict[str, Any]:
        ReviseFakeDemoPipeline.last_revise = {
            "project_id": project_id,
            "task_id": task_id,
            "source_generation_id": source_generation_id,
            "generation_id": generation_id,
            "instruction": instruction,
            "intents": intents,
            "variant": variant,
            "resume": resume,
        }
        emit(status="running", stage="parsing_edit_intent", progress=5, message="parse")
        emit(status="running", stage="applying_edit_intent", progress=12, message="apply")
        base = self.run_generation(
            project_id=project_id,
            task_id=task_id,
            generation_id=generation_id,
            structure=structure,
            user_brief=user_brief,
            assets=assets,
            emit=emit,
            resume=False,
            variant=variant or "high_click",
        )
        if base.get("ok"):
            base["intents"] = intents or []
            base["sourceGenerationId"] = source_generation_id
        return base


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


def _sample_plan(project_id: str, generation_id: str, *, variant: str = "high_click") -> dict[str, Any]:
    return {
        "id": generation_id,
        "projectId": project_id,
        "structureId": "video-structure-demo",
        "inventoryId": "inventory-demo",
        "gapReportId": "gap-demo",
        "variant": variant,
        "masterNarration": "demo narration",
        "storyboard": [{"id": "scene-1"}],
        "timeline": {"durationSec": 30.0, "tracks": []},
        "packagingPlan": {
            "styleSummary": "demo",
            "subtitle": {"density": "medium"},
            "titleCards": [],
            "transitions": [],
        },
        "completionActions": [],
    }


def _seed_source_generation(
    storage_root: Path,
    project_id: str,
    generation_id: str,
    *,
    variant: str = "high_click",
) -> None:
    generation_root = storage_root / "projects" / project_id / "generations" / generation_id
    generation_root.mkdir(parents=True, exist_ok=True)
    plan = _sample_plan(project_id, generation_id, variant=variant)
    (generation_root / "generation-plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")


def _prepare_project_with_structure(client: TestClient, tmp_path: Path) -> dict[str, Any]:
    project = client.post("/api/projects", json={"name": "Revise"}).json()
    video = tmp_path / "sample.mp4"
    video.write_bytes(b"fake-video")
    sample_id = client.post(
        f"/api/projects/{project['id']}/samples/upload",
        files={"file": ("sample.mp4", video.read_bytes(), "video/mp4")},
    ).json()["id"]
    client.post(f"/api/samples/{sample_id}/analyze")
    return project


def _create_source_generation(app_paths, project_id: str) -> str:
    from app.db.session import Database
    from app.services.project_store import ProjectStore

    store = ProjectStore(Database(app_paths["database_path"]))
    created = store.create_generation(
        project_id=project_id,
        task_id="task-source",
        status="succeeded",
        variant="high_click",
    )
    generation_id = created["id"]
    store.update_generation(generation_id, plan=_sample_plan(project_id, generation_id))
    _seed_source_generation(app_paths["storage_root"], project_id, generation_id)
    return generation_id


def test_revise_generation_returns_new_ids_and_intents(
    revise_client: TestClient,
    app_paths,
    tmp_path: Path,
) -> None:
    project = _prepare_project_with_structure(revise_client, tmp_path)
    generation_id = _create_source_generation(app_paths, project["id"])

    source_plan_bytes = (
        app_paths["storage_root"]
        / "projects"
        / project["id"]
        / "generations"
        / generation_id
        / "generation-plan.json"
    ).read_bytes()

    response = revise_client.post(
        f"/api/generations/{generation_id}/revise",
        json={"instruction": "开头更抓人一些，字幕少一点"},
    )
    assert response.status_code == 202
    body = response.json()
    assert body["sourceGenerationId"] == generation_id
    assert body["generationId"] != generation_id
    assert body["taskId"]
    assert len(body["intents"]) == 2
    assert body["intents"][0]["operation"] == "adjust_hook"
    assert body["intents"][1]["operation"] == "reduce_subtitles"

    edit_intent_path = (
        app_paths["storage_root"]
        / "projects"
        / project["id"]
        / "generations"
        / body["generationId"]
        / "edit-intent.json"
    )
    assert edit_intent_path.is_file()
    persisted = json.loads(edit_intent_path.read_text(encoding="utf-8"))
    assert persisted["intents"] == body["intents"]

    source_after = (
        app_paths["storage_root"]
        / "projects"
        / project["id"]
        / "generations"
        / generation_id
        / "generation-plan.json"
    ).read_bytes()
    assert source_after == source_plan_bytes

    assert ReviseFakeDemoPipeline.last_revise is not None
    assert ReviseFakeDemoPipeline.last_revise["source_generation_id"] == generation_id
    assert ReviseFakeDemoPipeline.last_revise["generation_id"] == body["generationId"]


def test_revise_generation_404_for_missing_generation(revise_client: TestClient) -> None:
    response = revise_client.post(
        "/api/generations/does-not-exist/revise",
        json={"instruction": "开头更抓人一些"},
    )
    assert response.status_code == 404


def test_revise_generation_400_without_plan(
    revise_client: TestClient,
    app_paths,
    tmp_path: Path,
) -> None:
    project = _prepare_project_with_structure(revise_client, tmp_path)
    from app.db.session import Database
    from app.services.project_store import ProjectStore

    store = ProjectStore(Database(app_paths["database_path"]))
    created = store.create_generation(
        project_id=project["id"],
        task_id="task-empty",
        status="succeeded",
    )
    response = revise_client.post(
        f"/api/generations/{created['id']}/revise",
        json={"instruction": "开头更抓人一些"},
    )
    assert response.status_code == 400


def test_revise_generation_400_when_source_not_succeeded(
    revise_client: TestClient,
    app_paths,
    tmp_path: Path,
) -> None:
    project = _prepare_project_with_structure(revise_client, tmp_path)
    from app.db.session import Database
    from app.services.project_store import ProjectStore

    store = ProjectStore(Database(app_paths["database_path"]))
    created = store.create_generation(
        project_id=project["id"],
        task_id="task-failed",
        status="failed",
    )
    generation_id = created["id"]
    store.update_generation(generation_id, plan=_sample_plan(project["id"], generation_id))
    _seed_source_generation(app_paths["storage_root"], project["id"], generation_id)

    response = revise_client.post(
        f"/api/generations/{generation_id}/revise",
        json={"instruction": "开头更抓人一些"},
    )
    assert response.status_code == 400
    assert "succeeded" in response.json()["detail"]
