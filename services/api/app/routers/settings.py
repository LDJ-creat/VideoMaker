from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.db.session import Database
from app.services.cookie_store import CookieStore, UploadMode
from app.services.model_gateway_service import ModelGatewayService
from app.services.model_gateway_status import get_model_gateway_status

router = APIRouter(prefix="/api/settings", tags=["settings"])

_PROVIDER_NAMES = frozenset({"text", "vision", "tts", "image", "video"})


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


class ProviderSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    base_url: str | None = Field(default=None, alias="baseUrl")
    api_key: str | None = Field(default=None, alias="apiKey")
    model: str | None = None
    driver: str | None = None

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str | None) -> str | None:
        if value is None:
            return value
        stripped = value.strip()
        if not stripped:
            return stripped
        if not stripped.startswith(("http://", "https://")):
            raise ValueError("baseUrl must start with http:// or https://")
        return stripped


class ModelGatewaySettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    providers: dict[str, ProviderSettingsUpdate]

    @field_validator("providers")
    @classmethod
    def validate_providers(cls, value: dict[str, ProviderSettingsUpdate]) -> dict[str, ProviderSettingsUpdate]:
        unknown = set(value) - _PROVIDER_NAMES
        if unknown:
            raise ValueError(f"Unknown providers: {', '.join(sorted(unknown))}")
        for name, patch in value.items():
            if patch.model is not None and not str(patch.model).strip():
                raise ValueError(f"model must be non-empty when provided for provider '{name}'")
        return value


def _cookie_store(request: Request) -> CookieStore:
    return CookieStore(request.app.state.storage_root)


def _model_gateway_service(request: Request) -> ModelGatewayService:
    database: Database = request.app.state.db
    return ModelGatewayService(database, request.app.state.storage_root)


@router.get("/cookies", response_model=CookieStatusResponse)
def get_global_cookies(request: Request) -> dict[str, Any]:
    return _cookie_store(request).get_status()


@router.get("/model-gateway")
def get_model_gateway_settings(request: Request) -> dict[str, Any]:
    """Provider readiness from SQLite (no secrets). fixtureMode from VIDEOMAKER_FIXTURE_MODE env."""
    return get_model_gateway_status(request.app.state.db, request.app.state.storage_root)


@router.put("/model-gateway")
def put_model_gateway_settings(
    request: Request,
    body: ModelGatewaySettingsUpdate,
) -> dict[str, Any]:
    """Persist provider base URL, model, and API key (encrypted). Does not accept fixtureMode."""
    service = _model_gateway_service(request)
    updates: dict[str, dict[str, Any]] = {}
    for provider, patch in body.providers.items():
        entry: dict[str, Any] = {}
        if patch.base_url is not None:
            entry["baseUrl"] = patch.base_url
        if patch.api_key is not None:
            entry["apiKey"] = patch.api_key
        if patch.model is not None:
            entry["model"] = patch.model
        if patch.driver is not None:
            entry["driver"] = patch.driver
        if entry:
            updates[provider] = entry
    if not updates:
        raise HTTPException(status_code=400, detail="No provider fields to update")
    try:
        return service.update_providers(updates)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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
