from __future__ import annotations

import asyncio
import json
import os
import time
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.services.task_events import TaskEventService

router = APIRouter(prefix="/api/tasks", tags=["tasks"])

SSE_POLL_SEC = max(0.1, int(os.getenv("TASK_SSE_POLL_MS", "500")) / 1000.0)
SSE_HEARTBEAT_SEC = 15.0


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
async def stream_task_events(
    task_id: str,
    request: Request,
    once: bool = Query(default=False),
    after_id: int = Query(default=0, ge=0),
) -> StreamingResponse:
    task_service = service(request)
    if task_service.get_task(task_id) is None:
        raise HTTPException(status_code=404, detail="Task not found")

    async def events() -> AsyncIterator[str]:
        last_event_id = after_id
        last_activity = time.monotonic()

        while True:
            if await request.is_disconnected():
                return

            records = task_service.list_event_records(task_id, after_id=last_event_id)
            for record in records:
                last_event_id = int(record["eventId"])
                payload = {**record["event"], "eventId": last_event_id}
                yield f"event: task\ndata: {json.dumps(payload, separators=(',', ':'))}\n\n"
                last_activity = time.monotonic()

            current = task_service.get_task(task_id)
            if once or current is None:
                yield ": close\n\n"
                return

            if current is not None and task_service.is_terminal(current["status"]):
                yield ": close\n\n"
                return

            if time.monotonic() - last_activity >= SSE_HEARTBEAT_SEC:
                yield ": ping\n\n"
                last_activity = time.monotonic()

            await asyncio.sleep(SSE_POLL_SEC)

    return StreamingResponse(events(), media_type="text/event-stream")
