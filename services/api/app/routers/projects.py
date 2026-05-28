from __future__ import annotations

import mimetypes
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile, status
from pydantic import BaseModel, Field

from app.services.artifact_store import ArtifactStore
from app.services.cookie_store import CookieStore, UploadMode
from app.services.pipeline_runner import PipelineRunner
from app.services.project_store import ProjectStore
from app.services.task_events import TaskEventService

router = APIRouter(prefix="/api/projects", tags=["projects"])


class CreateProjectRequest(BaseModel):
    name: str | None = None


class CreateProjectResponse(BaseModel):
    id: str
    name: str
    createdAt: str


class UploadResponse(BaseModel):
    id: str
    taskId: str | None = Field(default=None, alias="taskId")


class SampleFromUrlRequest(BaseModel):
    url: str


class UserBriefPayload(BaseModel):
    topic: str | None = None
    productName: str | None = Field(default=None, alias="productName")
    sellingPoints: list[str] = Field(default_factory=list, alias="sellingPoints")
    targetAudience: str | None = Field(default=None, alias="targetAudience")
    tone: str | None = None
    mustMention: list[str] = Field(default_factory=list, alias="mustMention")
    avoidMention: list[str] = Field(default_factory=list, alias="avoidMention")

    model_config = {"populate_by_name": True}


class GenerationPlanResponse(BaseModel):
    generationId: str
    taskId: str | None = None
    gapReport: dict[str, Any] | None = None


def _project_store(request: Request) -> ProjectStore:
    return ProjectStore(request.app.state.db)


def _task_events(request: Request) -> TaskEventService:
    return TaskEventService(request.app.state.db)


def _artifact_store(request: Request) -> ArtifactStore:
    return ArtifactStore(request.app.state.storage_root)


def _pipeline_runner(request: Request) -> PipelineRunner:
    return request.app.state.pipeline_runner


def _infer_asset_type(filename: str, content_type: str | None) -> str:
    guessed, _ = mimetypes.guess_type(filename)
    mime = content_type or guessed or ""
    if mime.startswith("video/"):
        return "video"
    if mime.startswith("image/"):
        return "image"
    return "text"


@router.post("", status_code=status.HTTP_201_CREATED, response_model=CreateProjectResponse)
def create_project(payload: CreateProjectRequest, request: Request) -> dict[str, Any]:
    project = _project_store(request).create_project(payload.name)
    return project


@router.get("/{project_id}", response_model=CreateProjectResponse)
def get_project(project_id: str, request: Request) -> dict[str, Any]:
    project = _project_store(request).get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.post(
    "/{project_id}/samples/upload",
    status_code=status.HTTP_201_CREATED,
    response_model=UploadResponse,
)
async def upload_sample(
    project_id: str,
    request: Request,
    file: UploadFile = File(...),
) -> dict[str, Any]:
    if _project_store(request).get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")

    store = _project_store(request)
    created = store.create_sample(
        project_id=project_id,
        source_kind="local",
        status="uploaded",
    )
    sample_id = created["id"]
    suffix = Path(file.filename or "sample.mp4").suffix or ".mp4"
    relative_path = f"samples/{sample_id}/source{suffix}"
    destination = _artifact_store(request).resolve_project_path(project_id, relative_path)
    destination.write_bytes(await file.read())
    store.update_sample(sample_id, video_uri=str(destination))
    return {"id": sample_id, "taskId": None}


@router.get("/{project_id}/samples/active")
def get_active_sample(project_id: str, request: Request) -> dict[str, Any]:
    if _project_store(request).get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    sample = _project_store(request).get_latest_sample_with_video(project_id)
    if sample is None:
        raise HTTPException(status_code=404, detail="No sample with video file for project")
    return {
        "id": sample["id"],
        "status": sample["status"],
        "sourceKind": sample["sourceKind"],
        "hasStructure": sample.get("structure") is not None,
        "videoUri": sample.get("videoUri"),
    }


@router.post(
    "/{project_id}/samples/from-url",
    status_code=status.HTTP_201_CREATED,
    response_model=UploadResponse,
)
def import_sample_from_url(
    project_id: str,
    payload: SampleFromUrlRequest,
    request: Request,
) -> dict[str, Any]:
    if _project_store(request).get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")

    task = _task_events(request).create_task(
        project_id,
        stage="uploading",
        message="Queued URL sample import",
    )
    sample = _project_store(request).create_sample(
        project_id=project_id,
        source_kind="url",
        source_url=payload.url,
        status="importing",
        task_id=task["taskId"],
    )
    _pipeline_runner(request).start_url_import(
        project_id=project_id,
        sample_id=sample["id"],
        task_id=task["taskId"],
        url=payload.url,
    )
    return {"id": sample["id"], "taskId": task["taskId"]}


@router.post(
    "/{project_id}/assets/upload",
    status_code=status.HTTP_201_CREATED,
    response_model=UploadResponse,
)
async def upload_asset(
    project_id: str,
    request: Request,
    file: UploadFile = File(...),
) -> dict[str, Any]:
    if _project_store(request).get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")

    asset_id = str(uuid.uuid4())
    suffix = Path(file.filename or "asset.bin").suffix
    relative_path = f"assets/{asset_id}/source{suffix}"
    artifact_store = _artifact_store(request)
    destination = artifact_store.resolve_project_path(project_id, relative_path)
    destination.write_bytes(await file.read())

    asset_type = _infer_asset_type(file.filename or "", file.content_type)
    created = _project_store(request).add_asset(
        project_id=project_id,
        asset_type=asset_type,
        uri=str(destination),
        description=file.filename,
    )
    return {"id": created["id"]}


def _cookie_store(request: Request) -> CookieStore:
    return CookieStore(request.app.state.storage_root)


class CookieStatusResponse(BaseModel):
    configured: bool
    updatedAt: str | None = None
    domains: list[str] = []


@router.get("/{project_id}/cookies", response_model=CookieStatusResponse, deprecated=True)
def get_cookie_status(project_id: str, request: Request) -> dict[str, Any]:
    """Deprecated: use GET /api/settings/cookies (global, shared across projects)."""
    if _project_store(request).get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return _cookie_store(request).get_status()


@router.post("/{project_id}/cookies/upload", status_code=status.HTTP_201_CREATED, deprecated=True)
async def upload_cookies(
    project_id: str,
    request: Request,
    file: UploadFile = File(...),
    mode: UploadMode = "merge",
) -> dict[str, Any]:
    """Deprecated: use POST /api/settings/cookies/upload."""
    if _project_store(request).get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")

    filename = (file.filename or "cookies.txt").lower()
    if not filename.endswith(".txt"):
        raise HTTPException(
            status_code=400,
            detail="Cookie file must be a .txt file (Netscape cookies format)",
        )

    content = await file.read()
    if not content.strip():
        raise HTTPException(status_code=400, detail="Cookie file is empty")

    try:
        return _cookie_store(request).save_upload(content, mode=mode)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{project_id}/brief")
def save_brief(project_id: str, payload: UserBriefPayload, request: Request) -> dict[str, bool]:
    if _project_store(request).get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    _project_store(request).save_brief(project_id, payload.model_dump(by_alias=True, exclude_none=True))
    return {"ok": True}


@router.post(
    "/{project_id}/generation-plan",
    status_code=status.HTTP_201_CREATED,
    response_model=GenerationPlanResponse,
)
def create_generation_plan(project_id: str, request: Request) -> dict[str, Any]:
    store = _project_store(request)
    if store.get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")

    structure = store.get_latest_sample_structure(project_id)
    if structure is None:
        ready = store.get_latest_sample_with_video(project_id)
        if ready and ready.get("videoUri") and ready.get("structure") is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    "No analyzed sample structure for project. "
                    f"Run sample analysis on {ready['id']} first."
                ),
            )
        raise HTTPException(
            status_code=400,
            detail="No analyzed sample structure for project. Complete sample analysis first.",
        )

    brief = store.get_brief(project_id) or {
        "topic": "Demo topic",
        "sellingPoints": [],
        "mustMention": [],
        "avoidMention": [],
    }
    assets = store.list_assets(project_id)

    task = _task_events(request).create_task(
        project_id,
        stage="analyzing_assets",
        message="Queued generation plan",
    )
    generation = store.create_generation(project_id=project_id, task_id=task["taskId"], status="queued")
    _pipeline_runner(request).start_generation(
        project_id=project_id,
        generation_id=generation["id"],
        task_id=task["taskId"],
        structure=structure,
        user_brief=brief,
        assets=assets,
    )
    return {
        "generationId": generation["id"],
        "taskId": task["taskId"],
        "gapReport": None,
    }
