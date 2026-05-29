from __future__ import annotations

import mimetypes
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.services.artifact_store import ArtifactStore
from app.services.cookie_store import CookieStore, UploadMode
from app.services.generation_responses import build_latest_generations_response
from app.services.variant_registry import get_variant_label, resolve_requested_variants
from app.services.media_paths import asset_media_path, resolve_existing_file, sample_media_path
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


class ProjectListResponse(BaseModel):
    projects: list[CreateProjectResponse]


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


class GenerationPlanEntry(BaseModel):
    generationId: str = Field(alias="generationId")
    variant: str
    taskId: str = Field(alias="taskId")
    label: str

    model_config = {"populate_by_name": True}


class MultiVariantGenerationResponse(BaseModel):
    generations: list[GenerationPlanEntry]


class GenerationPlanRequest(BaseModel):
    brief: UserBriefPayload | None = None
    variants: list[str] | None = None


class BriefResponse(BaseModel):
    brief: dict[str, Any] | None = None


class ProjectAssetsResponse(BaseModel):
    assets: list[dict[str, Any]]


class SampleSummaryResponse(BaseModel):
    id: str
    status: str
    sourceKind: str
    hasStructure: bool
    videoUri: str | None = None
    sourceUrl: str | None = None
    fileName: str | None = None
    previewUrl: str | None = None


class ProjectSamplesResponse(BaseModel):
    samples: list[SampleSummaryResponse]


def _ensure_project(store: ProjectStore, project_id: str) -> None:
    if store.get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")


def _asset_with_preview(project_id: str, asset: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(asset)
    if asset.get("type") in {"video", "image"}:
        enriched["previewUrl"] = asset_media_path(project_id, asset["id"])
    return enriched


def _sample_summary(project_id: str, sample: dict[str, Any]) -> dict[str, Any]:
    video_uri = sample.get("videoUri")
    file_name = Path(video_uri).name if video_uri else None
    return {
        "id": sample["id"],
        "status": sample["status"],
        "sourceKind": sample["sourceKind"],
        "hasStructure": sample.get("structure") is not None,
        "videoUri": video_uri,
        "sourceUrl": sample.get("sourceUrl"),
        "fileName": file_name,
        "previewUrl": sample_media_path(project_id, sample["id"]) if video_uri else None,
    }


def _media_type_for_path(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(path.name)
    return guessed or "application/octet-stream"


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


@router.get("", response_model=ProjectListResponse)
def list_projects(request: Request) -> dict[str, Any]:
    projects = _project_store(request).list_projects()
    return {"projects": projects}


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


@router.get("/{project_id}/brief", response_model=BriefResponse)
def get_brief(project_id: str, request: Request) -> dict[str, Any]:
    store = _project_store(request)
    _ensure_project(store, project_id)
    return {"brief": store.get_brief(project_id)}


@router.get("/{project_id}/assets", response_model=ProjectAssetsResponse)
def list_project_assets(project_id: str, request: Request) -> dict[str, Any]:
    store = _project_store(request)
    _ensure_project(store, project_id)
    assets = [
        _asset_with_preview(project_id, asset)
        for asset in store.list_assets(project_id)
    ]
    return {"assets": assets}


@router.get("/{project_id}/media/samples/{sample_id}")
def stream_sample_media(project_id: str, sample_id: str, request: Request) -> FileResponse:
    store = _project_store(request)
    _ensure_project(store, project_id)
    sample = store.get_sample(sample_id)
    if sample is None or sample["projectId"] != project_id:
        raise HTTPException(status_code=404, detail="Sample not found")
    video_uri = sample.get("videoUri")
    if not video_uri:
        raise HTTPException(status_code=404, detail="Sample has no video file")
    path = resolve_existing_file(str(video_uri))
    if path is None:
        raise HTTPException(status_code=404, detail="Sample video file missing on disk")
    return FileResponse(path, media_type=_media_type_for_path(path), filename=path.name)


@router.get("/{project_id}/media/assets/{asset_id}")
def stream_asset_media(project_id: str, asset_id: str, request: Request) -> FileResponse:
    store = _project_store(request)
    _ensure_project(store, project_id)
    asset = store.get_asset(asset_id)
    if asset is None or asset["projectId"] != project_id:
        raise HTTPException(status_code=404, detail="Asset not found")
    if asset.get("type") not in {"video", "image"}:
        raise HTTPException(status_code=400, detail="Asset type is not previewable")
    path = resolve_existing_file(str(asset["uri"]))
    if path is None:
        raise HTTPException(status_code=404, detail="Asset file missing on disk")
    return FileResponse(path, media_type=_media_type_for_path(path), filename=path.name)


@router.get("/{project_id}/samples", response_model=ProjectSamplesResponse)
def list_project_samples(project_id: str, request: Request) -> dict[str, Any]:
    store = _project_store(request)
    _ensure_project(store, project_id)
    samples = store.list_samples(project_id)
    return {"samples": [_sample_summary(project_id, sample) for sample in samples]}


@router.get("/{project_id}/samples/active")
def get_active_sample(project_id: str, request: Request) -> dict[str, Any]:
    store = _project_store(request)
    _ensure_project(store, project_id)
    sample = store.get_latest_sample_with_video(project_id)
    if sample is None:
        raise HTTPException(status_code=404, detail="No sample with video file for project")
    return _sample_summary(project_id, sample)


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


@router.get("/{project_id}/generations/latest")
def get_latest_generation(project_id: str, request: Request) -> dict[str, Any]:
    """P1: returns latest completed generation per variant for frontend reload."""
    store = _project_store(request)
    _ensure_project(store, project_id)
    records = store.get_latest_generations_with_plan(project_id)
    if not records:
        raise HTTPException(status_code=404, detail="No completed generation for project")
    return build_latest_generations_response(records)


@router.post(
    "/{project_id}/generation-plan",
    status_code=status.HTTP_201_CREATED,
    response_model=MultiVariantGenerationResponse,
)
def create_generation_plan(
    project_id: str,
    request: Request,
    payload: GenerationPlanRequest | None = Body(default=None),
) -> dict[str, Any]:
    """P1: spawns one task + generation record per requested variant (default: high_click + high_conversion)."""
    store = _project_store(request)
    _ensure_project(store, project_id)

    if payload is not None and payload.brief is not None:
        store.save_brief(
            project_id,
            payload.brief.model_dump(by_alias=True, exclude_none=True),
        )

    try:
        variant_ids = resolve_requested_variants(None if payload is None else payload.variants)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

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

    generations: list[dict[str, Any]] = []
    for variant in variant_ids:
        task = _task_events(request).create_task(
            project_id,
            stage="analyzing_assets",
            message=f"Queued generation plan ({variant})",
        )
        generation = store.create_generation(
            project_id=project_id,
            task_id=task["taskId"],
            status="queued",
            variant=variant,
        )
        _pipeline_runner(request).start_generation(
            project_id=project_id,
            generation_id=generation["id"],
            task_id=task["taskId"],
            structure=structure,
            user_brief=brief,
            assets=assets,
            variant=variant,
        )
        generations.append(
            {
                "generationId": generation["id"],
                "variant": variant,
                "taskId": task["taskId"],
                "label": get_variant_label(variant),
            }
        )

    return {"generations": generations}
