from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request

from app.services.generation_responses import build_generation_plan_response
from app.services.project_store import ProjectStore

router = APIRouter(prefix="/api/generations", tags=["generations"])


def _project_store(request: Request) -> ProjectStore:
    return ProjectStore(request.app.state.db)


@router.get("/{generation_id}")
def get_generation(generation_id: str, request: Request) -> dict[str, Any]:
    record = _project_store(request).get_generation(generation_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Generation not found")

    return build_generation_plan_response(record)
