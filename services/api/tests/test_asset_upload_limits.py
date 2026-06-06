from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.asset_upload_limits import (
    asset_image_max_bytes,
    asset_text_max_bytes,
    asset_video_max_bytes,
    validate_asset_upload_size,
)
from app.routers.projects import _infer_asset_type


def test_infer_asset_type_rejects_unknown_mime() -> None:
    assert _infer_asset_type("archive.zip", "application/zip") is None
    assert _infer_asset_type("data.bin", "application/octet-stream") is None


def test_infer_asset_type_accepts_text_by_extension() -> None:
    assert _infer_asset_type("notes.md", None) == "text"
    assert _infer_asset_type("copy.txt", "text/plain") == "text"


def test_validate_asset_upload_size_enforces_video_limit() -> None:
    with pytest.raises(HTTPException) as exc_info:
        validate_asset_upload_size("video", asset_video_max_bytes() + 1)
    assert exc_info.value.status_code == 413


def test_validate_asset_upload_size_allows_within_limit() -> None:
    validate_asset_upload_size("image", asset_image_max_bytes())
    validate_asset_upload_size("text", asset_text_max_bytes())
