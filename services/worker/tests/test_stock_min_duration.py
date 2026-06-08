from __future__ import annotations

import math

import pytest

from app.providers.stock_media_provider import StockMediaProvider
from app.tools.image_gen_tool import ToolError


def test_pick_candidate_passes_ceil_target_as_pexels_min_duration() -> None:
    captured: dict[str, int | None] = {"min_duration": None}

    class RecordingPexels:
        def search_photos(self, query: str, *, orientation=None, per_page=15):
            return []

        def search_videos(
            self,
            query: str,
            *,
            orientation=None,
            per_page=15,
            min_duration=None,
            max_duration=None,
        ):
            captured["min_duration"] = min_duration
            return [
                {
                    "id": 99,
                    "duration": 16,
                    "tags": query.split(),
                    "url": "https://www.pexels.com/video/99/",
                    "user": {"name": "Contributor"},
                    "video_files": [{"link": "https://cdn.example/99.mp4", "width": 1920, "height": 1080}],
                }
            ]

        def download(self, url: str, dest_path) -> None:
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            dest_path.write_bytes(b"mp4")

    provider = StockMediaProvider(pexels_tool=RecordingPexels())  # type: ignore[arg-type]
    provider._materialize_video = lambda *args, **kwargs: (  # type: ignore[method-assign]
        {"type": "video", "uri": "/tmp/out.mp4"},
        {"source": "pexels"},
    )

    provider._pick_candidate(
        queries=["kitchen lifestyle"],
        prefer_video=True,
        orientation=None,
        target_duration_sec=15.7,
    )
    assert captured["min_duration"] == math.ceil(15.7)


def test_pick_candidate_raises_when_no_video_meets_target_duration() -> None:
    class ShortVideoPexels:
        def search_photos(self, query: str, *, orientation=None, per_page=15):
            return []

        def search_videos(
            self,
            query: str,
            *,
            orientation=None,
            per_page=15,
            min_duration=None,
            max_duration=None,
        ):
            return [{"id": 1, "duration": 15, "tags": query.split()}]

    provider = StockMediaProvider(pexels_tool=ShortVideoPexels())  # type: ignore[arg-type]
    with pytest.raises(ToolError) as exc:
        provider._pick_candidate(
            queries=["kitchen lifestyle"],
            prefer_video=True,
            orientation=None,
            target_duration_sec=15.7,
        )
    assert exc.value.code == "pexels_no_results"
