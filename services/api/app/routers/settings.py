from __future__ import annotations

import logging
from typing import Any, Literal

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.db.session import Database
from app.services.cookie_store import CookieStore, UploadMode
from app.services.model_gateway_probe import probe_model_gateway_provider
from app.services.model_gateway_service import ModelGatewayService
from app.services.model_gateway_status import get_model_gateway_status
from app.services.stock_media_service import StockMediaService

router = APIRouter(prefix="/api/settings", tags=["settings"])
logger = logging.getLogger(__name__)

_PROVIDER_NAMES = frozenset({"text", "vision", "videoUnderstanding", "tts", "image", "video"})


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


class ModelGatewayProviderProbeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    provider: Literal["text", "videoUnderstanding"]
    base_url: str | None = Field(default=None, alias="baseUrl")
    model: str | None = None
    api_key: str | None = Field(default=None, alias="apiKey")

    @field_validator("base_url")
    @classmethod
    def validate_probe_base_url(cls, value: str | None) -> str | None:
        if value is None:
            return value
        stripped = value.strip()
        if not stripped:
            return stripped
        if not stripped.startswith(("http://", "https://")):
            raise ValueError("baseUrl must start with http:// or https://")
        return stripped


class ModelGatewayPreferencesUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    direct_multimodal_analysis_enabled: bool | None = Field(
        default=None,
        alias="directMultimodalAnalysisEnabled",
    )


class ModelGatewaySettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    providers: dict[str, ProviderSettingsUpdate] | None = None
    preferences: ModelGatewayPreferencesUpdate | None = None

    @field_validator("providers")
    @classmethod
    def validate_providers(
        cls,
        value: dict[str, ProviderSettingsUpdate] | None,
    ) -> dict[str, ProviderSettingsUpdate] | None:
        if value is None:
            return value
        unknown = set(value) - _PROVIDER_NAMES
        if unknown:
            raise ValueError(f"Unknown providers: {', '.join(sorted(unknown))}")
        for name, patch in value.items():
            if patch.model is not None and not str(patch.model).strip():
                raise ValueError(f"model must be non-empty when provided for provider '{name}'")
        return value


class StockMediaSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    api_key: str | None = Field(default=None, alias="apiKey")


class StockMediaProbeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    api_key: str | None = Field(default=None, alias="apiKey")


def _cookie_store(request: Request) -> CookieStore:
    return CookieStore(request.app.state.storage_root)


def _model_gateway_service(request: Request) -> ModelGatewayService:
    database: Database = request.app.state.db
    return ModelGatewayService(database, request.app.state.storage_root)


def _stock_media_service(request: Request) -> StockMediaService:
    database: Database = request.app.state.db
    return StockMediaService(database, request.app.state.storage_root)


@router.get("/cookies", response_model=CookieStatusResponse)
def get_global_cookies(request: Request) -> dict[str, Any]:
    return _cookie_store(request).get_status()


@router.get("/model-gateway")
def get_model_gateway_settings(request: Request) -> dict[str, Any]:
    """Provider readiness from SQLite (no secrets). fixtureMode from VIDEOMAKER_FIXTURE_MODE env."""
    return get_model_gateway_status(request.app.state.db, request.app.state.storage_root)


@router.post("/model-gateway/test")
def post_model_gateway_provider_test(
    request: Request,
    body: ModelGatewayProviderProbeRequest,
) -> dict[str, Any]:
    """Probe a single model provider using saved or inline credentials."""
    database: Database = request.app.state.db
    try:
        return probe_model_gateway_provider(
            database,
            request.app.state.storage_root,
            provider=body.provider,
            base_url=body.base_url,
            model=body.model,
            api_key=body.api_key,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/model-gateway")
def put_model_gateway_settings(
    request: Request,
    body: ModelGatewaySettingsUpdate,
) -> dict[str, Any]:
    """Persist provider base URL, model, API key, and analysis preferences."""
    service = _model_gateway_service(request)
    updates: dict[str, dict[str, Any]] = {}
    if body.providers:
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
    preference_updates: dict[str, Any] | None = None
    if body.preferences is not None:
        preference_updates = {}
        if body.preferences.direct_multimodal_analysis_enabled is not None:
            preference_updates["directMultimodalAnalysisEnabled"] = (
                body.preferences.direct_multimodal_analysis_enabled
            )
    if not updates and not preference_updates:
        raise HTTPException(status_code=400, detail="No provider fields or preferences to update")
    try:
        return service.update_settings(
            provider_updates=updates or None,
            preference_updates=preference_updates,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/stock-media")
def get_stock_media_settings(request: Request) -> dict[str, Any]:
    return _stock_media_service(request).get_status()


@router.put("/stock-media")
def put_stock_media_settings(
    request: Request,
    body: StockMediaSettingsUpdate,
) -> dict[str, Any]:
    if body.api_key is None:
        raise HTTPException(status_code=400, detail="apiKey is required")
    try:
        return _stock_media_service(request).update_settings(api_key=body.api_key)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Failed to persist stock media settings")
        raise HTTPException(
            status_code=500,
            detail="Failed to save Pexels API key",
        ) from exc


@router.post("/stock-media/test")
def post_stock_media_test(
    request: Request,
    body: StockMediaProbeRequest | None = None,
) -> dict[str, Any]:
    inline_key = body.api_key if body is not None else None
    try:
        return _stock_media_service(request).probe(api_key=inline_key)
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
