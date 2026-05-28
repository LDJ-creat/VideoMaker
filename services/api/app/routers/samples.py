from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request, status

from app.services.pipeline_runner import PipelineRunner
from app.services.project_store import ProjectStore
from app.services.task_events import TaskEventService

router = APIRouter(prefix="/api/samples", tags=["samples"])


def _project_store(request: Request) -> ProjectStore:
    return ProjectStore(request.app.state.db)


def _task_events(request: Request) -> TaskEventService:
    return TaskEventService(request.app.state.db)


def _pipeline_runner(request: Request) -> PipelineRunner:
    return request.app.state.pipeline_runner


@router.post("/{sample_id}/analyze", status_code=status.HTTP_200_OK)
def analyze_sample(sample_id: str, request: Request) -> dict[str, str]:
    store = _project_store(request)
    sample = store.get_sample(sample_id)
    if sample is None:
        raise HTTPException(status_code=404, detail="Sample not found")
    if not sample.get("videoUri"):
        latest = store.get_latest_sample_with_video(sample["projectId"])
        if latest is not None:
            sample_id = latest["id"]
            sample = latest
        else:
            raise HTTPException(
                status_code=400,
                detail="Sample has no video file. Upload a local sample video or fix URL import first.",
            )

    if sample.get("taskId"):
        existing_task = _task_events(request).get_task(sample["taskId"])
        if existing_task and existing_task.get("status") in ("running", "retrying"):
            raise HTTPException(
                status_code=409,
                detail="Sample analysis already in progress. Wait or retry the existing task.",
            )
        if sample.get("status") == "failed" and existing_task and existing_task.get("status") == "failed":
            raise HTTPException(
                status_code=409,
                detail=f"Sample analysis failed. POST /api/tasks/{sample['taskId']}/retry to resume from checkpoint.",
            )

    task = _task_events(request).create_task(
        sample["projectId"],
        stage="extracting_metadata",
        message="Queued sample analysis",
    )
    _pipeline_runner(request).start_sample_analysis(
        project_id=sample["projectId"],
        sample_id=sample_id,
        task_id=task["taskId"],
        video_uri=sample["videoUri"],
    )
    store.update_sample(sample_id, status="analyzing", task_id=task["taskId"])
    return {"taskId": task["taskId"]}


@router.get("/{sample_id}/structure")
def get_sample_structure(sample_id: str, request: Request) -> dict[str, Any]:
    sample = _project_store(request).get_sample(sample_id)
    if sample is None:
        raise HTTPException(status_code=404, detail="Sample not found")
    structure = sample.get("structure")
    if structure is None:
        raise HTTPException(status_code=404, detail="Structure not available")
    return structure


@router.get("/{sample_id}/analysis")
def get_sample_analysis(sample_id: str, request: Request) -> dict[str, Any]:
    return get_sample_structure(sample_id, request)
