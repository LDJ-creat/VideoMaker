from __future__ import annotations

import base64
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

LANGFUSE_DEFAULT_BASE_URL = "https://cloud.langfuse.com"

# Langfuse Cloud data regions (see https://langfuse.com/security/data-regions)
LANGFUSE_CLOUD_REGIONS: tuple[str, ...] = (
    LANGFUSE_DEFAULT_BASE_URL,
    "https://us.cloud.langfuse.com",
    "https://jp.cloud.langfuse.com",
    "https://hipaa.cloud.langfuse.com",
)


def resolve_langfuse_base_url() -> str | None:
    return (
        os.getenv("LANGFUSE_BASE_URL", "").strip()
        or os.getenv("LANGFUSE_HOST", "").strip()
        or None
    )


def detect_langfuse_base_url(public_key: str, secret_key: str) -> str | None:
    """Return the first Langfuse Cloud region that accepts the API key pair."""
    try:
        import httpx
    except ImportError:
        logger.warning("httpx not available; cannot auto-detect Langfuse region")
        return None

    auth = base64.b64encode(f"{public_key}:{secret_key}".encode()).decode()
    for base_url in LANGFUSE_CLOUD_REGIONS:
        try:
            response = httpx.get(
                f"{base_url}/api/public/projects",
                headers={"Authorization": f"Basic {auth}"},
                timeout=10.0,
            )
            if response.status_code == 200:
                return base_url
        except Exception:
            logger.debug("Langfuse region probe failed for %s", base_url, exc_info=True)
    return None


def resolve_langfuse_client_kwargs(
    *,
    public_key: str,
    secret_key: str,
    auto_detect_region: bool = True,
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "public_key": public_key,
        "secret_key": secret_key,
    }
    base_url = resolve_langfuse_base_url()
    if not base_url and auto_detect_region:
        base_url = detect_langfuse_base_url(public_key, secret_key)
        if base_url:
            logger.info("Langfuse: auto-detected cloud region %s", base_url)
    if base_url:
        kwargs["base_url"] = base_url
    return kwargs
