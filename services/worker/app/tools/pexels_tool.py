from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from app.tools.image_gen_tool import ToolError


@dataclass
class PexelsSearchResult:
    photos: list[dict[str, Any]]
    videos: list[dict[str, Any]]


class PexelsTool:
    PHOTO_SEARCH_URL = "https://api.pexels.com/v1/search"
    VIDEO_SEARCH_URL = "https://api.pexels.com/videos/search"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        client: httpx.Client | None = None,
        fixture_mode: bool | None = None,
    ) -> None:
        self._api_key = (api_key or os.getenv("VIDEOMAKER_PEXELS_API_KEY", "")).strip()
        self._client = client
        self._fixture_mode = (
            fixture_mode
            if fixture_mode is not None
            else os.getenv("VIDEOMAKER_FIXTURE_MODE", "false").strip().lower()
            in {"1", "true", "yes"}
        )

    def _headers(self) -> dict[str, str]:
        if not self._api_key:
            raise ToolError(
                code="pexels_unauthorized",
                message="Pexels API key is not configured",
                retryable=False,
            )
        return {"Authorization": self._api_key}

    def _get_client(self) -> httpx.Client:
        if self._client is not None:
            return self._client
        return httpx.Client(timeout=30.0)

    def search_photos(
        self,
        query: str,
        *,
        orientation: str | None = None,
        per_page: int = 15,
    ) -> list[dict[str, Any]]:
        if self._fixture_mode:
            return [
                {
                    "id": 1001,
                    "alt": query,
                    "width": 1920,
                    "height": 1080,
                    "url": "https://www.pexels.com/photo/fixture/",
                    "photographer": "Fixture Photographer",
                    "src": {"original": "fixture://photo.jpg"},
                }
            ]
        params: dict[str, Any] = {"query": query, "per_page": per_page}
        if orientation in {"landscape", "portrait", "square"}:
            params["orientation"] = orientation
        data = self._request(self.PHOTO_SEARCH_URL, params)
        photos = data.get("photos")
        return photos if isinstance(photos, list) else []

    def search_videos(
        self,
        query: str,
        *,
        orientation: str | None = None,
        per_page: int = 15,
        min_duration: int | None = None,
        max_duration: int | None = None,
    ) -> list[dict[str, Any]]:
        if self._fixture_mode:
            return [
                {
                    "id": 2001,
                    "tags": query.split(),
                    "duration": 8,
                    "url": "https://www.pexels.com/video/fixture/",
                    "user": {"name": "Fixture Videographer"},
                    "video_files": [
                        {
                            "quality": "hd",
                            "width": 1920,
                            "height": 1080,
                            "link": "fixture://video.mp4",
                        }
                    ],
                }
            ]
        params: dict[str, Any] = {"query": query, "per_page": per_page}
        if orientation in {"landscape", "portrait", "square"}:
            params["orientation"] = orientation
        if min_duration is not None and min_duration > 0:
            params["min_duration"] = int(min_duration)
        if max_duration is not None and max_duration > 0:
            params["max_duration"] = int(max_duration)
        data = self._request(self.VIDEO_SEARCH_URL, params)
        videos = data.get("videos")
        return videos if isinstance(videos, list) else []

    def download(self, url: str, dest_path: Path) -> None:
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        if url.startswith("fixture://"):
            if url.endswith(".mp4"):
                dest_path.write_bytes(b"\x00\x00\x00\x18ftypmp42")
            else:
                dest_path.write_bytes(b"\x89PNG\r\n\x1a\n")
            return
        with self._get_client() as client:
            response = client.get(url, follow_redirects=True)
            if response.status_code >= 400:
                raise ToolError(
                    code="pexels_download_failed",
                    message=f"Pexels download failed with status {response.status_code}",
                    retryable=response.status_code >= 500,
                )
            dest_path.write_bytes(response.content)

    def _request(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        with self._get_client() as client:
            response = client.get(url, headers=self._headers(), params=params)
            if response.status_code == 401:
                raise ToolError(
                    code="pexels_unauthorized",
                    message="Pexels API key is invalid",
                    retryable=False,
                )
            if response.status_code == 429:
                raise ToolError(
                    code="pexels_rate_limited",
                    message="Pexels API rate limit exceeded",
                    retryable=True,
                )
            if response.status_code >= 400:
                raise ToolError(
                    code="pexels_request_failed",
                    message=f"Pexels request failed with status {response.status_code}",
                    retryable=response.status_code >= 500,
                )
            payload = response.json()
            if not isinstance(payload, dict):
                raise ToolError(
                    code="pexels_invalid_response",
                    message="Pexels response was not a JSON object",
                    retryable=False,
                )
            return payload


def best_photo_src(photo: dict[str, Any]) -> str | None:
    src = photo.get("src")
    if isinstance(src, dict):
        for key in ("large2x", "large", "original", "medium"):
            value = src.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def best_video_file(video: dict[str, Any]) -> dict[str, Any] | None:
    files = video.get("video_files")
    if not isinstance(files, list) or not files:
        return None
    hd = [item for item in files if isinstance(item, dict) and item.get("quality") == "hd"]
    pool = hd or [item for item in files if isinstance(item, dict)]
    if not pool:
        return None
    return max(pool, key=lambda item: int(item.get("width") or 0))
