from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient


class FakeDemoPipeline:
    last_cookies_path: str | None = None
    last_resume: bool = False
    last_retry_task_id: str | None = None
    last_variant: str = "default"

    def analyze_sample(
        self,
        *,
        project_id: str,
        task_id: str,
        sample_id: str,
        video_path: str | Path | None = None,
        source_url: str | None = None,
        cookies_path: str | Path | None = None,
        emit: Any,
        resume: bool = False,
    ) -> dict[str, Any]:
        FakeDemoPipeline.last_cookies_path = str(cookies_path) if cookies_path else None
        FakeDemoPipeline.last_resume = resume
        FakeDemoPipeline.last_retry_task_id = task_id
        emit(
            status="running",
            stage="extracting_metadata",
            progress=20,
            message="fake analysis",
        )
        structure = {
            "id": f"video-structure-{project_id}",
            "projectId": project_id,
            "sourceVideoId": sample_id,
            "version": "p0-v1",
            "metadata": {"durationSec": 10.0},
            "narrative": {"summary": "fake", "segments": []},
            "rhythm": {
                "totalDurationSec": 10.0,
                "shotCount": 1,
                "avgShotDurationSec": 10.0,
                "tempo": "medium",
                "beatPoints": [],
                "shotBoundaries": [],
            },
            "packaging": {"visualDensity": "medium"},
            "slots": [],
            "evidence": [],
            "confidence": 0.5,
        }
        emit(
            status="succeeded",
            stage="completed",
            progress=100,
            message="fake analysis done",
        )
        return {"ok": True, "structure": structure}

    def run_generation(
        self,
        *,
        project_id: str,
        task_id: str,
        generation_id: str,
        structure: dict[str, Any],
        user_brief: dict[str, Any],
        assets: list[dict[str, Any]],
        emit: Any,
        resume: bool = False,
        variant: str = "default",
        sample_selection: dict[str, Any] | None = None,
        generation_run_id: str | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        FakeDemoPipeline.last_resume = resume
        FakeDemoPipeline.last_retry_task_id = task_id
        FakeDemoPipeline.last_variant = variant
        emit(status="running", stage="analyzing_assets", progress=10, message="fake gen")
        inventory = {
            "id": f"inventory-{project_id}",
            "projectId": project_id,
            "userBrief": user_brief,
            "assets": assets,
            "extractedFacts": [],
            "candidateMoments": [],
        }
        gap_report = {
            "id": f"gap-{project_id}-{variant}",
            "projectId": project_id,
            "structureId": structure["id"],
            "inventoryId": inventory["id"],
            "slotMatches": [],
            "missingSlots": [],
            "weakSlots": [],
            "summary": "ok",
        }
        plan = {
            "id": generation_id,
            "projectId": project_id,
            "structureId": structure["id"],
            "inventoryId": inventory["id"],
            "gapReportId": gap_report["id"],
            "variant": variant,
            "masterNarration": "",
            "storyboard": [],
            "timeline": {"durationSec": 10.0, "tracks": []},
            "packagingPlan": {
                "styleSummary": "fake",
                "subtitle": {},
                "titleCards": [],
                "transitions": [],
            },
            "completionActions": [],
        }
        emit(status="succeeded", stage="completed", progress=100, message="fake gen done")
        return {
            "ok": True,
            "inventory": inventory,
            "gapReport": gap_report,
            "plan": plan,
        }

    def revise_script_draft(
        self,
        *,
        project_id: str,
        task_id: str,
        generation_id: str,
        scope: str,
        instruction: str,
        structure: dict[str, Any] | None,
        emit: Any,
    ) -> dict[str, Any]:
        _ = (project_id, task_id, structure, emit)
        return {
            "ok": True,
            "draft": {
                "generationId": generation_id,
                "projectId": project_id,
                "variant": "high_click",
                "masterNarration": f"revised-{instruction}",
                "masterNarrationStatus": "draft",
                "storyboard": [],
                "storyboardStatus": "draft",
            },
            "summary": f"fake revise {scope}",
            "revisionId": "rev-fake-1",
        }


@pytest.fixture()
def p0_client(app_paths):
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


def test_create_project_and_get(p0_client: TestClient):
    created = p0_client.post("/api/projects", json={"name": "Demo"}).json()
    assert created["id"]
    fetched = p0_client.get(f"/api/projects/{created['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["name"] == "Demo"


def test_update_project_name(p0_client: TestClient):
    created = p0_client.post("/api/projects", json={"name": "Old Name"}).json()
    project_id = created["id"]

    response = p0_client.patch(
        f"/api/projects/{project_id}",
        json={"name": "New Name"},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "New Name"

    fetched = p0_client.get(f"/api/projects/{project_id}")
    assert fetched.json()["name"] == "New Name"

    listed = p0_client.get("/api/projects").json()["projects"]
    assert listed[0]["name"] == "New Name"

    invalid = p0_client.patch(
        f"/api/projects/{project_id}",
        json={"name": "   "},
    )
    assert invalid.status_code == 422


def test_list_projects(p0_client: TestClient):
    empty = p0_client.get("/api/projects")
    assert empty.status_code == 200
    assert empty.json()["projects"] == []

    first = p0_client.post("/api/projects", json={"name": "First"}).json()
    second = p0_client.post("/api/projects", json={"name": "Second"}).json()

    listed = p0_client.get("/api/projects").json()["projects"]
    assert [project["id"] for project in listed] == [second["id"], first["id"]]
    assert [project["name"] for project in listed] == ["Second", "First"]


def test_delete_project_cascades_metadata_and_storage(
    p0_client: TestClient,
    app_paths,
    tmp_path: Path,
):
    project = p0_client.post("/api/projects", json={"name": "To Delete"}).json()
    project_id = project["id"]

    video = tmp_path / "sample.mp4"
    video.write_bytes(b"fake-video")
    p0_client.post(
        f"/api/projects/{project_id}/samples/upload",
        files={"file": ("sample.mp4", video.read_bytes(), "video/mp4")},
    )
    p0_client.post(
        f"/api/projects/{project_id}/brief",
        json={"topic": "delete me"},
    )

    storage_root = app_paths["storage_root"]
    project_dir = storage_root / "projects" / project_id
    assert project_dir.is_dir()

    response = p0_client.delete(f"/api/projects/{project_id}")
    assert response.status_code == 204

    assert p0_client.get(f"/api/projects/{project_id}").status_code == 404
    assert p0_client.get("/api/projects").json()["projects"] == []
    assert not project_dir.exists()

    missing = p0_client.delete(f"/api/projects/{project_id}")
    assert missing.status_code == 404


def test_list_project_samples(p0_client: TestClient, tmp_path: Path):
    project = p0_client.post("/api/projects", json={"name": "Samples"}).json()
    video = tmp_path / "sample.mp4"
    video.write_bytes(b"fake-video")

    upload = p0_client.post(
        f"/api/projects/{project['id']}/samples/upload",
        files={"file": ("sample.mp4", video.read_bytes(), "video/mp4")},
    )
    assert upload.status_code == 201
    sample_id = upload.json()["id"]

    listed = p0_client.get(f"/api/projects/{project['id']}/samples").json()["samples"]
    assert len(listed) == 1
    assert listed[0]["id"] == sample_id
    assert listed[0]["previewUrl"] == f"/api/projects/{project['id']}/media/samples/{sample_id}"


def test_upload_sample_and_analyze(p0_client: TestClient, tmp_path: Path):
    project = p0_client.post("/api/projects", json={"name": "P"}).json()
    video = tmp_path / "sample.mp4"
    video.write_bytes(b"fake-video")

    upload = p0_client.post(
        f"/api/projects/{project['id']}/samples/upload",
        files={"file": ("sample.mp4", video.read_bytes(), "video/mp4")},
    )
    assert upload.status_code == 201
    sample_id = upload.json()["id"]

    analyze = p0_client.post(f"/api/samples/{sample_id}/analyze")
    assert analyze.status_code == 200
    task_id = analyze.json()["taskId"]

    task = p0_client.get(f"/api/tasks/{task_id}").json()
    assert task["status"] == "succeeded"

    structure = p0_client.get(f"/api/samples/{sample_id}/structure")
    assert structure.status_code == 200
    assert structure.json()["projectId"] == project["id"]


def test_upload_global_cookies_and_url_import_uses_cookies(p0_client: TestClient):
    cookie_bytes = b"# Netscape HTTP Cookie File\n.example.com\tTRUE\t/\tFALSE\t0\tname\tvalue\n"
    upload = p0_client.post(
        "/api/settings/cookies/upload",
        files={"file": ("cookies.txt", cookie_bytes, "text/plain")},
    )
    assert upload.status_code == 201
    status = p0_client.get("/api/settings/cookies")
    assert status.status_code == 200
    assert status.json()["configured"] is True

    project = p0_client.post("/api/projects", json={"name": "Cookies"}).json()
    FakeDemoPipeline.last_cookies_path = None
    p0_client.post(
        f"/api/projects/{project['id']}/samples/from-url",
        json={"url": "https://example.com/video"},
    )
    assert FakeDemoPipeline.last_cookies_path is not None


def test_url_import_returns_task(p0_client: TestClient):
    project = p0_client.post("/api/projects", json={"name": "URL"}).json()
    response = p0_client.post(
        f"/api/projects/{project['id']}/samples/from-url",
        json={"url": "https://example.com/video"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["taskId"]
    task = p0_client.get(f"/api/tasks/{body['taskId']}").json()
    assert task["status"] == "succeeded"


def test_asset_brief_and_generation(p0_client: TestClient, tmp_path: Path):
    project = p0_client.post("/api/projects", json={"name": "Gen"}).json()
    video = tmp_path / "sample.mp4"
    video.write_bytes(b"v")
    sample_id = p0_client.post(
        f"/api/projects/{project['id']}/samples/upload",
        files={"file": ("sample.mp4", video.read_bytes(), "video/mp4")},
    ).json()["id"]
    p0_client.post(f"/api/samples/{sample_id}/analyze")

    image = tmp_path / "asset.jpg"
    image.write_bytes(b"jpg")
    asset = p0_client.post(
        f"/api/projects/{project['id']}/assets/upload",
        files={"file": ("asset.jpg", image.read_bytes(), "image/jpeg")},
    )
    assert asset.status_code == 201

    brief = p0_client.post(
        f"/api/projects/{project['id']}/brief",
        json={
            "topic": "果汁机",
            "sellingPoints": ["便携"],
            "mustMention": [],
            "avoidMention": [],
        },
    )
    assert brief.status_code == 200
    assert brief.json()["ok"] is True

    generation = p0_client.post(f"/api/projects/{project['id']}/generation-plan")
    assert generation.status_code == 201
    body = generation.json()
    assert "generations" in body
    assert len(body["generations"]) == 2
    variants = {entry["variant"] for entry in body["generations"]}
    assert variants == {"high_click", "high_conversion"}
    task_ids = {entry["taskId"] for entry in body["generations"]}
    generation_ids = {entry["generationId"] for entry in body["generations"]}
    assert len(task_ids) == 2
    assert len(generation_ids) == 2

    first = body["generations"][0]
    task = p0_client.get(f"/api/tasks/{first['taskId']}").json()
    assert task["status"] == "succeeded"

    result = p0_client.get(f"/api/generations/{first['generationId']}")
    assert result.status_code == 200
    payload = result.json()
    assert payload["id"] == first["generationId"]
    assert payload.get("gapReport") is not None

    latest = p0_client.get(f"/api/projects/{project['id']}/generations/latest")
    assert latest.status_code == 200
    latest_payload = latest.json()
    assert "generations" in latest_payload
    assert len(latest_payload["generations"]) == 2
    latest_by_variant = {entry["variant"]: entry for entry in latest_payload["generations"]}
    assert latest_by_variant["high_click"]["plan"].get("gapReport") is not None
    assert latest_by_variant["high_conversion"]["plan"].get("gapReport") is not None
    assert latest_by_variant["high_click"]["plan"].get("timeline") is not None


def test_brief_assets_and_media_persistence(p0_client: TestClient, tmp_path: Path) -> None:
    project = p0_client.post("/api/projects", json={"name": "Persist"}).json()
    project_id = project["id"]

    brief_payload = {
        "topic": "防晒喷雾",
        "sellingPoints": ["轻薄"],
        "mustMention": [],
        "avoidMention": [],
    }
    p0_client.post(f"/api/projects/{project_id}/brief", json=brief_payload)
    fetched = p0_client.get(f"/api/projects/{project_id}/brief")
    assert fetched.status_code == 200
    assert fetched.json()["brief"]["topic"] == "防晒喷雾"

    video = tmp_path / "sample.mp4"
    video.write_bytes(b"fake-video")
    sample_id = p0_client.post(
        f"/api/projects/{project_id}/samples/upload",
        files={"file": ("sample.mp4", video.read_bytes(), "video/mp4")},
    ).json()["id"]

    image = tmp_path / "asset.jpg"
    image.write_bytes(b"jpg-bytes")
    asset_id = p0_client.post(
        f"/api/projects/{project_id}/assets/upload",
        files={"file": ("asset.jpg", image.read_bytes(), "image/jpeg")},
    ).json()["id"]

    assets = p0_client.get(f"/api/projects/{project_id}/assets").json()["assets"]
    assert len(assets) == 1
    assert assets[0]["previewUrl"].endswith(f"/media/assets/{asset_id}")

    media = p0_client.get(f"/api/projects/{project_id}/media/samples/{sample_id}")
    assert media.status_code == 200
    assert media.headers["content-type"].startswith("video/")


def test_generation_plan_accepts_brief_body(p0_client: TestClient, tmp_path: Path) -> None:
    project = p0_client.post("/api/projects", json={"name": "BriefGen"}).json()
    project_id = project["id"]
    video = tmp_path / "sample.mp4"
    video.write_bytes(b"v")
    sample_id = p0_client.post(
        f"/api/projects/{project_id}/samples/upload",
        files={"file": ("sample.mp4", video.read_bytes(), "video/mp4")},
    ).json()["id"]
    p0_client.post(f"/api/samples/{sample_id}/analyze")

    generation = p0_client.post(
        f"/api/projects/{project_id}/generation-plan",
        json={"brief": {"topic": "用户主题", "sellingPoints": ["SPF50"], "mustMention": [], "avoidMention": []}},
    )
    assert generation.status_code == 201
    brief = p0_client.get(f"/api/projects/{project_id}/brief").json()["brief"]
    assert brief["topic"] == "用户主题"


def test_retry_stale_running_sample_analysis_uses_resume(
    p0_client: TestClient, tmp_path: Path
) -> None:
    project = p0_client.post("/api/projects", json={"name": "Stale Running"}).json()
    video = tmp_path / "sample.mp4"
    video.write_bytes(b"fake-video")
    sample_id = p0_client.post(
        f"/api/projects/{project['id']}/samples/upload",
        files={"file": ("sample.mp4", video.read_bytes(), "video/mp4")},
    ).json()["id"]

    analyze = p0_client.post(f"/api/samples/{sample_id}/analyze")
    task_id = analyze.json()["taskId"]

    p0_client.post(
        f"/api/tasks/{task_id}/events",
        json={
            "status": "running",
            "stage": "extracting_metadata",
            "progress": 5,
            "message": "stale running after reload",
        },
    )

    FakeDemoPipeline.last_resume = False
    retry = p0_client.post(f"/api/tasks/{task_id}/retry")
    assert retry.status_code == 200
    assert retry.json()["status"] == "retrying"
    assert FakeDemoPipeline.last_resume is True
    assert FakeDemoPipeline.last_retry_task_id == task_id


def test_retry_failed_sample_analysis_uses_resume(p0_client: TestClient, tmp_path: Path) -> None:
    project = p0_client.post("/api/projects", json={"name": "Retry"}).json()
    video = tmp_path / "sample.mp4"
    video.write_bytes(b"fake-video")
    sample_id = p0_client.post(
        f"/api/projects/{project['id']}/samples/upload",
        files={"file": ("sample.mp4", video.read_bytes(), "video/mp4")},
    ).json()["id"]

    analyze = p0_client.post(f"/api/samples/{sample_id}/analyze")
    task_id = analyze.json()["taskId"]
    assert p0_client.get(f"/api/tasks/{task_id}").json()["status"] == "succeeded"

    p0_client.post(
        f"/api/tasks/{task_id}/events",
        json={
            "status": "failed",
            "stage": "transcribing",
            "progress": 45,
            "message": "simulated failure",
            "error": {"code": "fast_whisper_failed", "message": "boom", "retryable": True},
        },
    )

    FakeDemoPipeline.last_resume = False
    retry = p0_client.post(f"/api/tasks/{task_id}/retry")
    assert retry.status_code == 200
    assert retry.json()["status"] == "retrying"
    assert FakeDemoPipeline.last_resume is True
    assert FakeDemoPipeline.last_retry_task_id == task_id
    assert p0_client.get(f"/api/tasks/{task_id}").json()["status"] == "succeeded"
