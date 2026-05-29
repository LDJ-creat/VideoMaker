from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile, status
from pydantic import BaseModel

from app.services.cookie_store import CookieStore, UploadMode
from app.services.model_gateway_status import get_model_gateway_status

router = APIRouter(prefix="/api/settings", tags=["settings"])


class CookieStatusResponse(BaseModel):
    configured: bool
    updatedAt: str | None = None
    domains: list[str] = []
    uploadMode: str | None = None


class CookieUploadResponse(BaseModel):
    ok: bool
    configured: bool
    updatedAt: str | None = None
    domains: list[str] = []
    mergedDomainsFromUpload: list[str] = []
    mode: str


def _cookie_store(request: Request) -> CookieStore:
    return CookieStore(request.app.state.storage_root)


@router.get("/cookies", response_model=CookieStatusResponse)
def get_global_cookies(request: Request) -> dict[str, Any]:
    return _cookie_store(request).get_status()


@router.get("/model-gateway")
def get_model_gateway_settings() -> dict[str, Any]:
    """Return ModelGateway provider readiness from process env (no secrets).

    Env vars mirror ``services/worker/app/gateway/config.py``:
    ``TEXT_*``, ``VISION_*``, ``TTS_*``, ``IMAGE_*``, ``VIDEO_*``,
    and ``VIDEOMAKER_FIXTURE_MODE``.
    """
    return get_model_gateway_status()


@router.post("/cookies/upload", status_code=status.HTTP_201_CREATED, response_model=CookieUploadResponse)
async def upload_global_cookies(
    request: Request,
    file: UploadFile = File(...),
    mode: UploadMode = Query(
        default="merge",
        description="merge: update only domains in this file; replace: overwrite all cookies",
    ),
) -> dict[str, Any]:
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
