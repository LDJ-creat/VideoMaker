from __future__ import annotations

import logging
from pathlib import Path

from video.poster import extract_video_poster

logger = logging.getLogger(__name__)


def try_extract_sample_poster(video_path: Path, poster_path: Path | None = None) -> dict:
    target = poster_path or (video_path.parent / "poster.jpg")
    result = extract_video_poster(video_path, target)
    if not result.get("ok"):
        logger.warning(
            "poster extract failed for %s: %s",
            video_path,
            result.get("error"),
        )
    return result
