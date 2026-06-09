from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile, status
from pydantic import BaseModel, Field

from app.services.artifact_store import ArtifactStore
from app.services.generation_responses import build_generation_plan_response
from app.services.generation_run_store import GenerationRunStore
from app.services.pipeline_runner import PipelineRunner
from app.services.poster_extract import try_extract_sample_poster
from app.services.project_store import ProjectStore
from app.services.sample_recommender import SampleRecommender
from app.services.sample_selection_store import SampleSelectionStore
from app.services.task_events import TaskEventService
from app.services.upload_batch_store import UploadBatchStore

router = APIRouter(prefix="/api/projects", tags=["sample-selection"])


class AnalyzeBatchRequest(BaseModel):
    sample_ids: list[str] | None = Field(default=None, alias="sampleIds")
    upload_batch_id: str | None = Field(default=None, alias="uploadBatchId")

    model_config = {"populate_by_name": True}


class UpdateSampleSelectionRequest(BaseModel):
    primary_sample_id: str | None = Field(default=None, alias="primarySampleId")
    reference_sample_ids: list[str] = Field(default_factory=list, alias="referenceSampleIds")
    active_upload_batch_id: str | None = Field(default=None, alias="activeUploadBatchId")

    model_config = {"populate_by_name": True}


def _project_store(request: Request) -> ProjectStore:
    return ProjectStore(request.app.state.db)


def _batch_store(request: Request) -> UploadBatchStore:
    return UploadBatchStore(request.app.state.db)


def _selection_store(request: Request) -> SampleSelectionStore:
    return SampleSelectionStore(request.app.state.db)


def _run_store(request: Request) -> GenerationRunStore:
    return GenerationRunStore(request.app.state.db)


def _artifact_store(request: Request) -> ArtifactStore:
    return ArtifactStore(request.app.state.storage_root)


def _task_events(request: Request) -> TaskEventService:
    return TaskEventService(request.app.state.db)


def _pipeline_runner(request: Request) -> PipelineRunner:
    return request.app.state.pipeline_runner


def _recommender(request: Request) -> SampleRecommender:
    db = request.app.state.db
    return SampleRecommender(
        _project_store(request),
        _selection_store(request),
        _batch_store(request),
    )


def _ensure_project(store: ProjectStore, project_id: str) -> None:
    if store.get_project(project_id) is None:
        raise HTTPException(status_code=404, detail="Project not found")


def _max_concurrent_analysis() -> int:
    raw = os.getenv("VIDEOMAKER_MAX_CONCURRENT_SAMPLE_ANALYSIS", "2")
    try:
        return max(1, int(raw))
    except ValueError:
        return 2


@router.post("/{project_id}/samples/upload-batch", status_code=status.HTTP_201_CREATED)
async def upload_sample_batch(
    project_id: str,
    request: Request,
    files: list[UploadFile] = File(...),
) -> dict[str, Any]:
    _ensure_project(_project_store(request), project_id)
    if not files:
        raise HTTPException(status_code=400, detail="At least one file is required")

    store = _project_store(request)
    batch_store = _batch_store(request)
    artifacts = _artifact_store(request)

    batch = batch_store.create_batch(project_id=project_id, status="uploading")
    samples: list[dict[str, Any]] = []

    for file in files:
        created = store.create_sample(
            project_id=project_id,
            source_kind="local",
            status="uploaded",
            upload_batch_id=batch["id"],
        )
        sample_id = created["id"]
        suffix = Path(file.filename or "sample.mp4").suffix or ".mp4"
        relative_path = f"samples/{sample_id}/source{suffix}"
        destination = artifacts.resolve_project_path(project_id, relative_path)
        destination.write_bytes(await file.read())
        store.update_sample(sample_id, video_uri=str(destination))
        try_extract_sample_poster(destination)
        batch_store.add_sample_to_batch(batch["id"], sample_id)
        samples.append({"id": sample_id, "taskId": None})

    batch_store.update_batch_status(batch["id"], status="uploading")
    return {"batchId": batch["id"], "samples": samples}


@router.get("/{project_id}/upload-batches")
def list_upload_batches(project_id: str, request: Request) -> dict[str, Any]:
    _ensure_project(_project_store(request), project_id)
    store = _project_store(request)
    batch_store = _batch_store(request)
    batches = batch_store.list_batches(project_id)
    enriched: list[dict[str, Any]] = []
    for batch in batches:
        sample_summaries = []
        for sample_id in batch["sampleIds"]:
            sample = store.get_sample(sample_id)
            if sample is None:
                continue
            sample_summaries.append(
                {
                    "id": sample["id"],
                    "status": sample["status"],
                    "hasStructure": sample.get("structure") is not None,
                    "uploadBatchId": sample.get("uploadBatchId"),
                }
            )
        enriched.append({**batch, "samples": sample_summaries})
    return {"batches": enriched}


@router.post("/{project_id}/samples/analyze-batch")
def analyze_sample_batch(
    project_id: str,
    request: Request,
    payload: AnalyzeBatchRequest | None = None,
) -> dict[str, Any]:
    _ensure_project(_project_store(request), project_id)
    store = _project_store(request)
    runner = _pipeline_runner(request)
    tasks_events = _task_events(request)

    target_ids: list[str] = []
    if payload and payload.sample_ids:
        target_ids = list(payload.sample_ids)
    elif payload and payload.upload_batch_id:
        batch = _batch_store(request).get_batch(payload.upload_batch_id)
        if batch is None or batch["projectId"] != project_id:
            raise HTTPException(status_code=404, detail="Upload batch not found")
        target_ids = list(batch["sampleIds"])
    else:
        target_ids = [
            sample["id"]
            for sample in store.list_samples_with_meta(project_id)
            if sample.get("sourceKind") != "knowledge"
            and sample.get("status") in {"uploaded", "failed"}
            and sample.get("videoUri")
        ]

    tasks: list[dict[str, str]] = []
    for sample_id in target_ids:
        sample = store.get_sample(sample_id)
        if sample is None or sample["projectId"] != project_id:
            continue
        if not sample.get("videoUri"):
            continue
        if sample.get("status") == "analyzed" and sample.get("structure"):
            continue
        if sample.get("taskId"):
            existing_task = tasks_events.get_task(sample["taskId"])
            if existing_task and existing_task.get("status") in ("running", "retrying"):
                tasks.append({"sampleId": sample_id, "taskId": sample["taskId"]})
                continue

        task = tasks_events.create_task(
            project_id,
            stage="extracting_metadata",
            message="Queued sample analysis",
        )
        store.update_sample(sample_id, status="queued", task_id=task["taskId"])
        runner.enqueue_sample_analysis(
            project_id=project_id,
            sample_id=sample_id,
            task_id=task["taskId"],
            video_uri=str(sample["videoUri"]),
        )
        tasks.append({"sampleId": sample_id, "taskId": task["taskId"]})

    batch_id = payload.upload_batch_id if payload else None
    if batch_id:
        batch = _batch_store(request).get_batch(batch_id)
        if batch is not None:
            statuses = {}
            for sample_id in batch["sampleIds"]:
                row = store.get_sample(str(sample_id))
                statuses[str(sample_id)] = str(row.get("status", "unknown")) if row else "unknown"
            _batch_store(request).refresh_batch_status(batch_id, statuses)

    return {"tasks": tasks, "maxConcurrent": _max_concurrent_analysis()}


@router.post("/{project_id}/samples/recommend")
def recommend_samples(project_id: str, request: Request) -> dict[str, Any]:
    _ensure_project(_project_store(request), project_id)
    recommendation = _recommender(request).recommend(project_id)
    return {"recommendation": recommendation}


@router.get("/{project_id}/samples/selection")
def get_sample_selection(project_id: str, request: Request) -> dict[str, Any]:
    _ensure_project(_project_store(request), project_id)
    selection = _recommender(request).ensure_selection(project_id)
    return {"selection": selection}


@router.put("/{project_id}/samples/selection")
def update_sample_selection(
    project_id: str,
    payload: UpdateSampleSelectionRequest,
    request: Request,
) -> dict[str, Any]:
    _ensure_project(_project_store(request), project_id)
    try:
        selection = _recommender(request).update_selection(
            project_id,
            primary_sample_id=payload.primary_sample_id,
            reference_sample_ids=payload.reference_sample_ids,
            active_upload_batch_id=payload.active_upload_batch_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"selection": selection}


@router.post("/{project_id}/samples/selection/reset")
def reset_sample_selection(project_id: str, request: Request) -> dict[str, Any]:
    _ensure_project(_project_store(request), project_id)
    selection = _recommender(request).reset_selection(project_id)
    return {"selection": selection}


@router.get("/{project_id}/generation-runs")
def list_generation_runs(
    project_id: str,
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    _ensure_project(_project_store(request), project_id)
    runs = _run_store(request).list_runs(project_id, limit=limit)
    return {"runs": runs}


def _load_run_provenance(
    *,
    storage_root: Path,
    project_id: str,
    generation_ids: list[str],
    provenance_id: str | None,
) -> dict[str, Any] | None:
    if not provenance_id or not generation_ids:
        return None
    for generation_id in generation_ids:
        path = (
            storage_root
            / "projects"
            / project_id
            / "generations"
            / generation_id
            / "structure-provenance.json"
        )
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            return payload
    return None


@router.get("/{project_id}/generation-runs/{run_id}")
def get_generation_run(project_id: str, run_id: str, request: Request) -> dict[str, Any]:
    _ensure_project(_project_store(request), project_id)
    run = _run_store(request).get_run(run_id)
    if run is None or run["projectId"] != project_id:
        raise HTTPException(status_code=404, detail="Generation run not found")

    store = _project_store(request)
    generations: list[dict[str, Any]] = []
    for generation_id in run["generationIds"]:
        record = store.get_generation(generation_id)
        if record is None:
            continue
        try:
            plan = build_generation_plan_response(
                record,
                storage_root=request.app.state.storage_root,
            )
        except HTTPException:
            plan = None
        generations.append(
            {
                "generationId": generation_id,
                "variant": record.get("variant"),
                "status": record.get("status"),
                "plan": plan,
            }
        )
    provenance = _load_run_provenance(
        storage_root=request.app.state.storage_root,
        project_id=project_id,
        generation_ids=run["generationIds"],
        provenance_id=run.get("provenanceId"),
    )
    return {"run": run, "generations": generations, "provenance": provenance}
