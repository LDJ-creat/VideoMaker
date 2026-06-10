from __future__ import annotations

import mimetypes
import os
import threading
import uuid
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, BackgroundTasks, Body, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.asset_upload_limits import validate_asset_upload_size
from app.services.artifact_store import ArtifactStore
from app.services.cookie_store import CookieStore, UploadMode
from app.services.knowledge_recommender import KnowledgeRecommender
from app.services.knowledge_store import KnowledgeStore
from app.services.knowledge_template_bootstrap import (
    KnowledgeTemplateBootstrapError,
    create_project_from_knowledge_template,
)
from app.services.generation_responses import build_latest_generations_response
from app.services.generation_run_store import GenerationRunStore
from app.services.sample_recommender import SampleRecommender
from app.services.sample_selection_store import SampleSelectionStore
from app.services.upload_batch_store import UploadBatchStore
from app.services.variant_registry import get_variant_label, resolve_requested_variants
from app.services.media_paths import asset_media_path, resolve_existing_file, sample_media_path
from app.services.poster_service import pick_project_cover_url, sample_poster_media_url
from app.services.pipeline_runner import PipelineRunner
from app.services.poster_extract import try_extract_sample_poster
from app.services.project_store import ProjectStore
from app.services.task_events import TaskEventService

router = APIRouter(prefix="/api/projects", tags=["projects"])


class CreateProjectRequest(BaseModel):
    name: str | None = None


class UpdateProjectRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)


class CreateProjectFromKnowledgeTemplateRequest(BaseModel):
    name: str = Field(min_length=1)
    category_slug: str = Field(alias="categorySlug", min_length=1)
    primary_entry_id: str = Field(alias="primaryEntryId", min_length=1)
    reference_entry_ids: list[str] = Field(
        default_factory=list,
        alias="referenceEntryIds",
        max_length=2,
    )

    model_config = {"populate_by_name": True}


class CreateProjectResponse(BaseModel):
    id: str
    name: str
    createdAt: str
    coverUrl: str | None = Field(default=None, alias="coverUrl")

    model_config = {"populate_by_name": True}


class ProjectListResponse(BaseModel):
    projects: list[CreateProjectResponse]


class UploadResponse(BaseModel):
    id: str
    taskId: str | None = Field(default=None, alias="taskId")


class SampleFromUrlRequest(BaseModel):
    url: str


class DurationTargetPayload(BaseModel):
    target_sec: float = Field(alias="targetSec")
    min_sec: float | None = Field(default=None, alias="minSec")
    max_sec: float | None = Field(default=None, alias="maxSec")
    recommended_sec: float | None = Field(default=None, alias="recommendedSec")
    source: str | None = None

    model_config = {"populate_by_name": True}


class UserBriefPayload(BaseModel):
    content_category: str | None = Field(default=None, alias="contentCategory")
    topic: str | None = None
    creative_goal: str | None = Field(default=None, alias="creativeGoal")
    subject_name: str | None = Field(default=None, alias="subjectName")
    productName: str | None = Field(default=None, alias="productName")
    key_points: list[str] = Field(default_factory=list, alias="keyPoints")
    sellingPoints: list[str] = Field(default_factory=list, alias="sellingPoints")
    targetAudience: str | None = Field(default=None, alias="targetAudience")
    tone: str | None = None
    mustMention: list[str] = Field(default_factory=list, alias="mustMention")
    avoidMention: list[str] = Field(default_factory=list, alias="avoidMention")
    supplemental_notes: str | None = Field(default=None, alias="supplementalNotes")
    duration_target: DurationTargetPayload | None = Field(default=None, alias="durationTarget")
    aspect_ratio: Literal["9:16", "16:9", "1:1"] | None = Field(default=None, alias="aspectRatio")

    model_config = {"populate_by_name": True}


class GenerationPlanEntry(BaseModel):
    generationId: str = Field(alias="generationId")
    variant: str
    taskId: str = Field(alias="taskId")
    label: str

    model_config = {"populate_by_name": True}


class SampleSelectionOverride(BaseModel):
    primary_sample_id: str = Field(alias="primarySampleId")
    reference_sample_ids: list[str] = Field(default_factory=list, alias="referenceSampleIds")

    model_config = {"populate_by_name": True}


class MultiVariantGenerationResponse(BaseModel):
    generationRunId: str | None = Field(default=None, alias="generationRunId")
    generations: list[GenerationPlanEntry]

    model_config = {"populate_by_name": True}


class GenerationPlanRequest(BaseModel):
    brief: UserBriefPayload | None = None
    variants: list[str] | None = None
    sample_selection: SampleSelectionOverride | None = Field(default=None, alias="sampleSelection")

    model_config = {"populate_by_name": True}


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
    posterUrl: str | None = Field(default=None, alias="posterUrl")
    uploadBatchId: str | None = Field(default=None, alias="uploadBatchId")
    taskId: str | None = Field(default=None, alias="taskId")

    model_config = {"populate_by_name": True}


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


def _sample_summary(
    project_id: str,
    sample: dict[str, Any],
    *,
    batch_store: UploadBatchStore | None = None,
    storage_root: Path | None = None,
) -> dict[str, Any]:
    video_uri = sample.get("videoUri")
    file_name = Path(video_uri).name if video_uri else None
    upload_batch_id = sample.get("uploadBatchId")
    batch_created_at: str | None = None
    if upload_batch_id and batch_store is not None:
        batch = batch_store.get_batch(str(upload_batch_id))
        if batch is not None:
            batch_created_at = batch.get("createdAt")
    poster_url: str | None = None
    if storage_root is not None and video_uri:
        poster_url = sample_poster_media_url(
            storage_root,
            project_id=project_id,
            sample_id=str(sample["id"]),
        )
    return {
        "id": sample["id"],
        "status": sample["status"],
        "sourceKind": sample["sourceKind"],
        "hasStructure": sample.get("structure") is not None,
        "videoUri": video_uri,
        "sourceUrl": sample.get("sourceUrl"),
        "fileName": file_name,
        "previewUrl": sample_media_path(project_id, sample["id"]) if video_uri else None,
        "posterUrl": poster_url,
        "uploadBatchId": upload_batch_id,
        "batchCreatedAt": batch_created_at,
        "taskId": sample.get("taskId"),
    }


def _knowledge_recommender(request: Request) -> KnowledgeRecommender:
    return KnowledgeRecommender(
        KnowledgeStore(request.app.state.db, request.app.state.storage_root),
        _project_store(request),
        storage_root=request.app.state.storage_root,
        database_path=request.app.state.db.path,
    )


def _sample_recommender(request: Request) -> SampleRecommender:
    db = request.app.state.db
    return SampleRecommender(
        _project_store(request),
        SampleSelectionStore(db),
        UploadBatchStore(db),
    )


def _ensure_selections_after_brief_save(
    *,
    project_id: str,
    database_path: Path,
    storage_root: Path,
) -> None:
    from app.db.session import Database

    db = Database(database_path)
    project_store = ProjectStore(db)
    knowledge_store = KnowledgeStore(db, storage_root)
    sample_recommender = SampleRecommender(
        project_store,
        SampleSelectionStore(db),
        UploadBatchStore(db),
    )
    knowledge_recommender = KnowledgeRecommender(
        knowledge_store,
        project_store,
        storage_root=storage_root,
        database_path=database_path,
    )
    sample_recommender.ensure_selection(project_id)
    knowledge_recommender.ensure_selection(project_id)


def _generation_run_store(request: Request) -> GenerationRunStore:
    return GenerationRunStore(request.app.state.db)


def _generation_artifact_path(
    storage_root: Path,
    project_id: str,
    generation_id: str,
    filename: str,
) -> Path:
    return (
        storage_root
        / "projects"
        / project_id
        / "generations"
        / generation_id
        / filename
    )


def _resolve_run_artifact_ids(
    *,
    storage_root: Path,
    project_id: str,
    generation_ids: list[str],
    run_id: str,
    has_references: bool,
    primary_structure_id: str,
) -> tuple[str, str | None]:
    if not has_references:
        return str(primary_structure_id), None

    synthesized_id = f"synthesized-{run_id}"
    provenance_id = f"provenance-{run_id}"
    has_synthesized = False
    has_provenance = False
    for generation_id in generation_ids:
        if _generation_artifact_path(
            storage_root,
            project_id,
            generation_id,
            "synthesized-structure.json",
        ).exists():
            has_synthesized = True
        if _generation_artifact_path(
            storage_root,
            project_id,
            generation_id,
            "structure-provenance.json",
        ).exists():
            has_provenance = True

    resolved_structure_id = synthesized_id if has_synthesized else str(primary_structure_id)
    resolved_provenance_id = provenance_id if has_provenance else None
    return resolved_structure_id, resolved_provenance_id


def _media_type_for_path(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(path.name)
    return guessed or "application/octet-stream"


_INLINE_MEDIA_SUFFIXES = {
    ".html",
    ".htm",
    ".css",
    ".js",
    ".mjs",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".svg",
    ".mp4",
    ".webm",
    ".mov",
    ".wav",
    ".mp3",
}


def _should_serve_media_inline(path: Path) -> bool:
    return path.suffix.lower() in _INLINE_MEDIA_SUFFIXES


def _media_file_response(path: Path) -> FileResponse:
    media_type = _media_type_for_path(path)
    if _should_serve_media_inline(path):
        return FileResponse(path, media_type=media_type)
    return FileResponse(path, media_type=media_type, filename=path.name)


def _project_store(request: Request) -> ProjectStore:
    return ProjectStore(request.app.state.db)


def _task_events(request: Request) -> TaskEventService:
    return TaskEventService(request.app.state.db)


def _artifact_store(request: Request) -> ArtifactStore:
    return ArtifactStore(request.app.state.storage_root)


def _pipeline_runner(request: Request) -> PipelineRunner:
    return request.app.state.pipeline_runner


def _infer_asset_type(filename: str, content_type: str | None) -> str | None:
    lowered = (filename or "").lower()
    guessed, _ = mimetypes.guess_type(filename)
    mime = (content_type or guessed or "").lower()
    if mime.startswith("video/"):
        return "video"
    if mime.startswith("image/"):
        return "image"
    if mime.startswith("text/") or lowered.endswith((".txt", ".md", ".markdown")):
        return "text"
    return None


@router.get("", response_model=ProjectListResponse)
def list_projects(request: Request) -> dict[str, Any]:
    store = _project_store(request)
    selection_store = SampleSelectionStore(request.app.state.db)
    storage_root = request.app.state.storage_root
    projects = []
    for project in store.list_projects():
        enriched = dict(project)
        enriched["coverUrl"] = pick_project_cover_url(
            storage_root,
            store,
            selection_store,
            str(project["id"]),
        )
        projects.append(enriched)
    return {"projects": projects}


@router.post("", status_code=status.HTTP_201_CREATED, response_model=CreateProjectResponse)
def create_project(payload: CreateProjectRequest, request: Request) -> dict[str, Any]:
    project = _project_store(request).create_project(payload.name)
    return project


@router.post("/from-knowledge-template", status_code=status.HTTP_201_CREATED)
def create_project_from_knowledge_template_route(
    payload: CreateProjectFromKnowledgeTemplateRequest,
    request: Request,
) -> dict[str, Any]:
    try:
        return create_project_from_knowledge_template(
            name=payload.name,
            category_slug=payload.category_slug,
            primary_entry_id=payload.primary_entry_id,
            reference_entry_ids=payload.reference_entry_ids,
            storage_root=request.app.state.storage_root,
            project_store=_project_store(request),
            knowledge_store=KnowledgeStore(
                request.app.state.db,
                request.app.state.storage_root,
            ),
            sample_selection_store=SampleSelectionStore(request.app.state.db),
        )
    except KnowledgeTemplateBootstrapError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/{project_id}", response_model=CreateProjectResponse)
def get_project(project_id: str, request: Request) -> dict[str, Any]:
    project = _project_store(request).get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.patch("/{project_id}", response_model=CreateProjectResponse)
def update_project(
    project_id: str,
    payload: UpdateProjectRequest,
    request: Request,
) -> dict[str, Any]:
    store = _project_store(request)
    _ensure_project(store, project_id)
    try:
        project = store.update_project(project_id, name=payload.name)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: str, request: Request) -> None:
    store = _project_store(request)
    deleted = store.delete_project(
        project_id,
        storage_root=request.app.state.storage_root,
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Project not found")


@router.post(
    "/{project_id}/samples/upload",
    status_code=status.HTTP_201_CREATED,
    response_model=UploadResponse,
)
async def upload_sample(
    project_id: str,
    request: Request,
    file: UploadFile = File(...),
    upload_batch_id: str | None = Query(default=None, alias="uploadBatchId"),
) -> dict[str, Any]:
    if _project_store(request).get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")

    store = _project_store(request)
    if upload_batch_id:
        batch = UploadBatchStore(request.app.state.db).get_batch(upload_batch_id)
        if batch is None or batch["projectId"] != project_id:
            raise HTTPException(status_code=404, detail="Upload batch not found")

    created = store.create_sample(
        project_id=project_id,
        source_kind="local",
        status="uploaded",
        upload_batch_id=upload_batch_id,
    )
    sample_id = created["id"]
    suffix = Path(file.filename or "sample.mp4").suffix or ".mp4"
    relative_path = f"samples/{sample_id}/source{suffix}"
    destination = _artifact_store(request).resolve_project_path(project_id, relative_path)
    destination.write_bytes(await file.read())
    store.update_sample(sample_id, video_uri=str(destination))
    try_extract_sample_poster(destination)
    if upload_batch_id:
        UploadBatchStore(request.app.state.db).add_sample_to_batch(upload_batch_id, sample_id)
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
    return _media_file_response(path)


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
    return _media_file_response(path)


def _resolve_project_media_file(
    request: Request,
    project_id: str,
    relative_path: str,
) -> Path:
    store = _project_store(request)
    _ensure_project(store, project_id)
    try:
        path = _artifact_store(request).resolve_project_path(project_id, relative_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Media file missing on disk")
    return path


@router.get("/{project_id}/media/file/{file_path:path}")
def stream_project_media_file(
    project_id: str,
    file_path: str,
    request: Request,
) -> FileResponse:
    path = _resolve_project_media_file(request, project_id, file_path)
    return _media_file_response(path)


@router.get("/{project_id}/media/artifacts/{artifact_id}")
def stream_project_artifact_media(
    project_id: str,
    artifact_id: str,
    request: Request,
) -> FileResponse:
    store = _project_store(request)
    _ensure_project(store, project_id)
    artifact = _artifact_store(request).get_artifact(
        request.app.state.db,
        artifact_id=artifact_id,
        project_id=project_id,
    )
    if artifact is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    path = resolve_existing_file(artifact["uri"])
    if path is None:
        raise HTTPException(status_code=404, detail="Artifact file missing on disk")
    return _media_file_response(path)


@router.get("/{project_id}/samples", response_model=ProjectSamplesResponse)
def list_project_samples(project_id: str, request: Request) -> dict[str, Any]:
    store = _project_store(request)
    _ensure_project(store, project_id)
    batch_store = _batch_store(request)
    storage_root: Path = request.app.state.storage_root
    samples = store.list_samples(project_id)
    return {
        "samples": [
            _sample_summary(
                project_id,
                sample,
                batch_store=batch_store,
                storage_root=storage_root,
            )
            for sample in samples
        ]
    }


def _batch_store(request: Request) -> UploadBatchStore:
    return UploadBatchStore(request.app.state.db)


@router.get("/{project_id}/samples/active")
def get_active_sample(project_id: str, request: Request) -> dict[str, Any]:
    store = _project_store(request)
    _ensure_project(store, project_id)
    batch_store = _batch_store(request)
    selection = _sample_recommender(request).ensure_selection(project_id)
    sample: dict[str, Any] | None = None
    if selection and selection.get("primarySampleId"):
        sample = store.get_sample(str(selection["primarySampleId"]))
    if sample is None or not sample.get("videoUri"):
        sample = store.get_latest_sample_with_video(project_id)
    if sample is None:
        raise HTTPException(status_code=404, detail="No sample with video file for project")
    return _sample_summary(
        project_id,
        sample,
        batch_store=batch_store,
        storage_root=request.app.state.storage_root,
    )


@router.post(
    "/{project_id}/samples/from-url",
    status_code=status.HTTP_201_CREATED,
    response_model=UploadResponse,
)
def import_sample_from_url(
    project_id: str,
    payload: SampleFromUrlRequest,
    request: Request,
    upload_batch_id: str | None = Query(default=None, alias="uploadBatchId"),
) -> dict[str, Any]:
    if _project_store(request).get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")

    if upload_batch_id:
        batch = UploadBatchStore(request.app.state.db).get_batch(upload_batch_id)
        if batch is None or batch["projectId"] != project_id:
            raise HTTPException(status_code=404, detail="Upload batch not found")

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
        upload_batch_id=upload_batch_id,
    )
    if upload_batch_id:
        UploadBatchStore(request.app.state.db).add_sample_to_batch(upload_batch_id, sample["id"])
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

    raw_bytes = await file.read()
    asset_type = _infer_asset_type(file.filename or "", file.content_type)
    if asset_type is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported asset file type; upload video, image, or text (.txt/.md)",
        )
    validate_asset_upload_size(asset_type, len(raw_bytes))

    asset_id = str(uuid.uuid4())
    suffix = Path(file.filename or "asset.bin").suffix
    relative_path = f"assets/{asset_id}/source{suffix}"
    artifact_store = _artifact_store(request)
    destination = artifact_store.resolve_project_path(project_id, relative_path)
    destination.write_bytes(raw_bytes)

    description = file.filename
    if asset_type == "text":
        try:
            preview = raw_bytes.decode("utf-8").strip()
            if preview:
                description = preview[:120] + ("…" if len(preview) > 120 else "")
        except UnicodeDecodeError:
            description = file.filename
    created = _project_store(request).add_asset(
        project_id=project_id,
        asset_type=asset_type,
        uri=str(destination),
        description=description,
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
def save_brief(
    project_id: str,
    payload: UserBriefPayload,
    request: Request,
    background_tasks: BackgroundTasks,
) -> dict[str, bool]:
    if _project_store(request).get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")
    _project_store(request).save_brief(project_id, payload.model_dump(by_alias=True, exclude_none=True))
    background_tasks.add_task(
        _ensure_selections_after_brief_save,
        project_id=project_id,
        database_path=request.app.state.db.path,
        storage_root=request.app.state.storage_root,
    )
    return {"ok": True}


@router.get("/{project_id}/generations/latest")
def get_latest_generation(project_id: str, request: Request) -> dict[str, Any]:
    """P1: returns latest completed generation per variant for frontend reload."""
    store = _project_store(request)
    _ensure_project(store, project_id)
    records = store.get_latest_generations_with_plan(project_id)
    if not records:
        raise HTTPException(status_code=404, detail="No completed generation for project")
    return build_latest_generations_response(
        records,
        storage_root=request.app.state.storage_root,
    )


@router.get("/{project_id}/duration-recommendation")
def get_duration_recommendation(project_id: str, request: Request) -> dict[str, Any]:
    from app.services.duration_recommendation import build_duration_recommendation

    store = _project_store(request)
    _ensure_project(store, project_id)
    sample_recommender = _sample_recommender(request)
    primary_structure: dict[str, Any] | None = None
    primary_sample: dict[str, Any] | None = None
    try:
        selection = sample_recommender.resolve_effective_selection(project_id)
        primary_sample, primary_structure, _refs = sample_recommender.load_structures_for_selection(
            selection
        )
    except ValueError:
        primary_structure = store.get_latest_sample_structure(project_id)
        primary_sample = store.get_latest_analyzed_sample(project_id)
    return build_duration_recommendation(
        structure=primary_structure,
        sample_id=str(primary_sample.get("id")) if isinstance(primary_sample, dict) else None,
    )


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

    sample_recommender = _sample_recommender(request)
    override = None
    if payload is not None and payload.sample_selection is not None:
        override = payload.sample_selection.model_dump(by_alias=True)

    if store.get_latest_analyzed_sample(project_id) is None:
        _knowledge_recommender(request).ensure_selection(project_id)
    else:
        sample_recommender.ensure_selection(project_id)

    try:
        variant_ids = resolve_requested_variants(None if payload is None else payload.variants)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        selection = sample_recommender.resolve_effective_selection(
            project_id,
            override=override,
        )
        _primary_sample, primary_structure, reference_structures = (
            sample_recommender.load_structures_for_selection(selection)
        )
    except ValueError as exc:
        ready = store.get_latest_sample_with_video(project_id)
        if ready and ready.get("videoUri") and ready.get("structure") is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    "No analyzed sample structure for project. "
                    f"Run sample analysis on {ready['id']} first."
                ),
            ) from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    run_store = _generation_run_store(request)
    generation_run = run_store.create_run(
        project_id=project_id,
        sample_selection_snapshot=selection,
        variant_ids=variant_ids,
    )
    run_id = generation_run["id"]

    sample_selection_payload: dict[str, Any] | None = None
    if reference_structures:
        sample_selection_payload = {
            "primarySampleId": selection.get("primarySampleId"),
            "referenceSampleIds": selection.get("referenceSampleIds") or [],
            "referenceStructures": reference_structures,
        }

    brief = store.get_brief(project_id) or {
        "topic": "Demo topic",
        "sellingPoints": [],
        "mustMention": [],
        "avoidMention": [],
    }
    assets = store.list_assets(project_id)

    completion_lock = threading.Lock()
    completion_state: dict[str, Any] = {
        "total": len(variant_ids),
        "by_generation": {},
    }
    has_references = bool(reference_structures)
    storage_root: Path = request.app.state.storage_root

    def on_generation_complete(generation_id: str, result: dict[str, Any]) -> None:
        with completion_lock:
            if result.get("paused"):
                completion_state["by_generation"][generation_id] = "paused"
            elif result.get("ok"):
                completion_state["by_generation"][generation_id] = "succeeded"
            else:
                completion_state["by_generation"][generation_id] = "failed"

            by_generation: dict[str, str] = completion_state["by_generation"]
            if len(by_generation) < int(completion_state["total"]):
                return

            statuses = list(by_generation.values())
            failed_count = sum(1 for status in statuses if status == "failed")
            succeeded_count = sum(1 for status in statuses if status == "succeeded")
            paused_count = sum(1 for status in statuses if status == "paused")
            if paused_count == len(statuses) and failed_count == 0:
                run_status = "awaiting_review"
            elif failed_count == 0 and succeeded_count == len(statuses):
                run_status = "completed"
            elif succeeded_count == 0:
                run_status = "partial_failed"
            else:
                run_status = "partial_failed"
            run = run_store.get_run(run_id)
            generation_ids = list(run["generationIds"]) if run else []
            synthesized_structure_id, provenance_id = _resolve_run_artifact_ids(
                storage_root=storage_root,
                project_id=project_id,
                generation_ids=generation_ids,
                run_id=run_id,
                has_references=has_references,
                primary_structure_id=str(primary_structure.get("id", "")),
            )
            run_store.update_run(
                run_id,
                status=run_status,
                synthesized_structure_id=synthesized_structure_id,
                provenance_id=provenance_id,
            )

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
            generation_run_id=run_id,
        )
        run_store.append_generation(run_id, generation["id"])
        _pipeline_runner(request).start_generation(
            project_id=project_id,
            generation_id=generation["id"],
            task_id=task["taskId"],
            structure=primary_structure,
            user_brief=brief,
            assets=assets,
            variant=variant,
            sample_selection=sample_selection_payload,
            generation_run_id=run_id,
            on_generation_complete=on_generation_complete,
            human_review_mode=os.getenv("VIDEOMAKER_HUMAN_REVIEW_MODE", "true").strip().lower()
            in {"1", "true", "yes", "on"},
        )
        generations.append(
            {
                "generationId": generation["id"],
                "variant": variant,
                "taskId": task["taskId"],
                "label": get_variant_label(variant),
            }
        )

    return {"generationRunId": run_id, "generations": generations}
