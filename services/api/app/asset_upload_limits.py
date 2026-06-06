from __future__ import annotations

import os

from fastapi import HTTPException, status


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def asset_video_max_bytes() -> int:
    return _env_int("VIDEOMAKER_VIDEO_UNDERSTANDING_MAX_MB", 50) * 1024 * 1024


def asset_image_max_bytes() -> int:
    return _env_int("VIDEOMAKER_ASSET_IMAGE_MAX_MB", 30) * 1024 * 1024


def asset_text_max_bytes() -> int:
    return _env_int("VIDEOMAKER_ASSET_TEXT_MAX_BYTES", 512) * 1024


def validate_asset_upload_size(asset_type: str, size_bytes: int) -> None:
    limits = {
        "video": asset_video_max_bytes(),
        "image": asset_image_max_bytes(),
        "text": asset_text_max_bytes(),
    }
    limit = limits.get(asset_type)
    if limit is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported asset type for upload size validation: {asset_type}",
        )
    if size_bytes > limit:
        limit_mb = max(1, round(limit / (1024 * 1024)))
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=(
                f"Asset file exceeds {limit_mb}MB limit for type '{asset_type}' "
                f"({size_bytes} bytes)"
            ),
        )
