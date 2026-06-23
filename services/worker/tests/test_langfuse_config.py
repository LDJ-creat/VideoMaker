from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.observability.langfuse_config import (
    LANGFUSE_CLOUD_REGIONS,
    detect_langfuse_base_url,
    resolve_langfuse_base_url,
    resolve_langfuse_client_kwargs,
)


def test_resolve_langfuse_base_url_prefers_base_url(
    monkeypatch,
) -> None:
    monkeypatch.setenv("LANGFUSE_BASE_URL", "https://jp.cloud.langfuse.com")
    monkeypatch.setenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
    assert resolve_langfuse_base_url() == "https://jp.cloud.langfuse.com"


def test_detect_langfuse_base_url_returns_first_matching_region() -> None:
    responses = {
        "https://cloud.langfuse.com": MagicMock(status_code=401),
        "https://us.cloud.langfuse.com": MagicMock(status_code=401),
        "https://jp.cloud.langfuse.com": MagicMock(status_code=200),
    }

    def fake_get(url: str, **kwargs):  # type: ignore[no-untyped-def]
        for base, response in responses.items():
            if url.startswith(base):
                return response
        raise AssertionError(f"unexpected url {url}")

    with patch("httpx.get", side_effect=fake_get):
        assert detect_langfuse_base_url("pk", "sk") == "https://jp.cloud.langfuse.com"


def test_resolve_langfuse_client_kwargs_auto_detects_when_unset(
    monkeypatch,
) -> None:
    monkeypatch.delenv("LANGFUSE_BASE_URL", raising=False)
    monkeypatch.delenv("LANGFUSE_HOST", raising=False)
    with patch(
        "app.observability.langfuse_config.detect_langfuse_base_url",
        return_value="https://jp.cloud.langfuse.com",
    ):
        kwargs = resolve_langfuse_client_kwargs(
            public_key="pk",
            secret_key="sk",
            auto_detect_region=True,
        )
    assert kwargs["base_url"] == "https://jp.cloud.langfuse.com"
    assert kwargs["public_key"] == "pk"


def test_langfuse_cloud_regions_include_japan() -> None:
    assert "https://jp.cloud.langfuse.com" in LANGFUSE_CLOUD_REGIONS
