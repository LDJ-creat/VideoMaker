from __future__ import annotations

import json
import time
from collections.abc import Iterator
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.services.task_events import TaskEventService

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


class CreateTaskRequest(BaseModel):
    project_id: str | None = Field(default=None, alias="projectId")
    stage: str
    message: str


class UpdateTaskRequest(BaseModel):
    status: str
    stage: str
    progress: int = Field(ge=0, le=100)
    message: str
    artifact_refs: list[dict[str, Any]] | None = Field(default=None, alias="artifactRefs")
    error: dict[str, Any] | None = None


def service(request: Request) -> TaskEventService:
    return TaskEventService(request.app.state.db)


@router.post("", status_code=status.HTTP_201_CREATED)
def create_task(payload: CreateTaskRequest, request: Request) -> dict[str, Any]:
    return service(request).create_task(
        project_id=payload.project_id,
        stage=payload.stage,
        message=payload.message,
    )


@router.get("/{task_id}")
def get_task(task_id: str, request: Request) -> dict[str, Any]:
    task = service(request).get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.post("/{task_id}/events")
def append_task_event(task_id: str, payload: UpdateTaskRequest, request: Request) -> dict[str, Any]:
    try:
        return service(request).update_task(
            task_id,
            status=payload.status,
            stage=payload.stage,
            progress=payload.progress,
            message=payload.message,
            artifact_refs=payload.artifact_refs,
            error=payload.error,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Task not found") from exc


@router.post("/{task_id}/retry")
def retry_task(task_id: str, request: Request) -> dict[str, Any]:
    task_service = service(request)
    current = task_service.get_task(task_id)
    if current is None:
        raise HTTPException(status_code=404, detail="Task not found")
    runner: Any = request.app.state.pipeline_runner
    try:
        return runner.retry_task(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Task not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{task_id}/cancel")
def cancel_task(task_id: str, request: Request) -> dict[str, Any]:
    current = service(request).get_task(task_id)
    if current is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return service(request).update_task(
        task_id,
        status="cancelled",
        stage=current["stage"],
        progress=current["progress"],
        message="Task cancelled",
    )


@router.get("/{task_id}/events")
def stream_task_events(
    task_id: str,
    request: Request,
    once: bool = Query(default=False),
) -> StreamingResponse:
    task_service = service(request)
    if task_service.get_task(task_id) is None:
        raise HTTPException(status_code=404, detail="Task not found")

    def events() -> Iterator[str]:
        emitted_count = 0
        while True:
            current_events = task_service.list_events(task_id)
            for event in current_events[emitted_count:]:
                emitted_count += 1
                yield f"event: task\ndata: {json.dumps(event, separators=(',', ':'))}\n\n"

            current = task_service.get_task(task_id)
            if once or current is None or task_service.is_terminal(current["status"]):
                return

            time.sleep(1)

    return StreamingResponse(events(), media_type="text/event-stream")
