from __future__ import annotations

from pathlib import Path
from typing import Any, TypedDict

from model_gateway.fixture import is_fixture_mode
from model_gateway.store import ModelGatewayStore
from model_gateway.text_probe import probe_text_chat
from model_gateway.video_probe import probe_video_understanding_chat

from app.db.session import Database

_SUPPORTED_PROVIDERS = frozenset({"text", "videoUnderstanding"})


class ProviderProbeResponse(TypedDict):
    provider: str
    ok: bool
    latencyMs: int
    message: str
    detail: str | None
    replyPreview: str | None


def probe_model_gateway_provider(
    database: Database,
    storage_root: Path,
    *,
    provider: str,
    base_url: str | None = None,
    model: str | None = None,
    api_key: str | None = None,
) -> ProviderProbeResponse:
    if provider not in _SUPPORTED_PROVIDERS:
        raise ValueError(f"Unsupported provider for probe: {provider}")

    if is_fixture_mode():
        return {
            "provider": provider,
            "ok": True,
            "latencyMs": 0,
            "message": "Fixture 模式：已跳过真实请求",
            "detail": None,
            "replyPreview": "OK",
        }

    store = ModelGatewayStore(database.path, storage_root)
    credentials = store.get_credentials()[provider]

    resolved_base_url = (base_url or credentials.base_url).strip()
    resolved_model = (model or credentials.model).strip()
    if api_key is not None and api_key.strip():
        resolved_api_key = api_key.strip()
    else:
        resolved_api_key = credentials.api_key

    result = (
        probe_video_understanding_chat(
            base_url=resolved_base_url,
            api_key=resolved_api_key,
            model=resolved_model,
        )
        if provider == "videoUnderstanding"
        else probe_text_chat(
            base_url=resolved_base_url,
            api_key=resolved_api_key,
            model=resolved_model,
        )
    )
    return {
        "provider": provider,
        "ok": result.ok,
        "latencyMs": result.latency_ms,
        "message": result.message,
        "detail": result.detail,
        "replyPreview": result.reply_preview,
    }
