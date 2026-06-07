from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.providers.completion_registry import MaterialContext, execute_completion_plan, register_default_providers
from app.providers.stock_media_provider import StockMediaProvider
from app.runtime.video_gen_quota import VideoGenQuota
from app.tools.ffmpeg_tool import FFmpegTool
from app.tools.pexels_tool import PexelsTool


def _trim_copy_ffmpeg() -> FFmpegTool:
    tool = FFmpegTool()

    def _trim(source_path: Path, output_path: Path, *, start_sec: float, duration_sec: float):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(source_path.read_bytes())
        return {}

    tool.trim_clip = _trim  # type: ignore[method-assign]
    return tool


def _action(slot_id: str) -> dict:
    return {
        "id": f"action-{slot_id}",
        "slotId": slot_id,
        "strategy": "stock_media_search",
        "provider": "stock_media_search",
        "reason": "缺少使用场景",
        "outputRef": f"completion://{slot_id}/stock_media_search",
    }


def test_stock_media_provider_downloads_fixture_video(tmp_path: Path) -> None:
    generated_root = tmp_path / "generated"
    generated_root.mkdir()
    ctx = MaterialContext(
        project_id="project-1",
        generation_id="gen-1",
        render_root=tmp_path / "render",
        generated_root=generated_root,
        gateway=MagicMock(),
        quota=VideoGenQuota(max_slots=1),
        inventory={"userBrief": {"topic": "kitchen", "sellingPoints": []}},
        slot_matches=[],
        storyboard=[
            {
                "id": "scene-1",
                "slotId": "slot-usage",
                "startSec": 0.0,
                "endSec": 3.0,
                "visual": "kitchen usage",
                "script": "start your day",
                "source": "generated",
            }
        ],
        structure={
            "slots": [
                {
                    "id": "slot-usage",
                    "role": "usage_scene",
                    "requiredAssetType": ["video"],
                    "scriptIntent": "展示厨房使用场景",
                }
            ]
        },
        emit_progress=lambda *_args, **_kwargs: None,
        register_artifact=lambda artifact_type, path: {
            "id": "art-1",
            "type": artifact_type,
            "uri": str(Path(path).resolve()),
            "createdAt": "2026-06-08T00:00:00Z",
        },
    )
    ctx.providers = {
        "stock_media_search": StockMediaProvider(
            pexels_tool=PexelsTool(api_key="fixture", fixture_mode=True),
            ffmpeg_tool=_trim_copy_ffmpeg(),
        )
    }
    results = execute_completion_plan([_action("slot-usage")], ctx, fail_fast=True, only_aigc=True)
    assert results[0]["ok"] is True
    assert results[0]["stockAttribution"]["source"] == "pexels"
    assert (generated_root / "slot-usage-stock.mp4").is_file()


def test_stock_media_provider_concatenates_long_slot_segments(tmp_path: Path) -> None:
    generated_root = tmp_path / "generated"
    generated_root.mkdir()
    download_counter = {"n": 0}

    class SegmentPexels(PexelsTool):
        def search_photos(self, query: str, *, orientation=None, per_page=15):
            return []

        def search_videos(self, query: str, *, orientation=None, per_page=15):
            return [
                {
                    "id": hash(query) % 10000,
                    "duration": 12,
                    "tags": [query],
                    "url": f"https://www.pexels.com/video/{hash(query)}/",
                    "user": {"name": "Contributor"},
                    "video_files": [
                        {
                            "link": f"https://cdn.example/{hash(query)}.mp4",
                            "width": 1280,
                            "height": 720,
                        }
                    ],
                }
            ]

        def download(self, url: str, output_path: Path) -> None:
            download_counter["n"] += 1
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(f"video-{download_counter['n']}".encode())

    ffmpeg = _trim_copy_ffmpeg()

    def _concat(clip_paths, output_path, **_kwargs):
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = "|".join(Path(path).read_text(encoding="utf-8", errors="ignore") for path in clip_paths)
        output_path.write_text(payload, encoding="utf-8")
        return {}

    ffmpeg.concat_clips = _concat  # type: ignore[method-assign]

    visual = "商务饭局、朋友聚会、家庭聚餐三类场景示范"
    ctx = MaterialContext(
        project_id="project-1",
        generation_id="gen-1",
        render_root=tmp_path / "render",
        generated_root=generated_root,
        gateway=MagicMock(),
        quota=VideoGenQuota(max_slots=0),
        inventory={"userBrief": {"topic": "为人处世", "sellingPoints": []}},
        slot_matches=[],
        storyboard=[
            {
                "id": "scene-4",
                "slotId": "slot-4",
                "startSec": 32.0,
                "endSec": 79.0,
                "visual": visual,
                "script": "不同场景规则示范",
                "source": "generated",
            }
        ],
        structure={
            "slots": [
                {
                    "id": "slot-4",
                    "role": "product_closeup",
                    "requiredAssetType": ["video"],
                    "scriptIntent": "展示多场景社交行为",
                }
            ]
        },
        emit_progress=lambda *_args, **_kwargs: None,
        register_artifact=lambda artifact_type, path: {
            "id": "art-1",
            "type": artifact_type,
            "uri": str(Path(path).resolve()),
            "createdAt": "2026-06-08T00:00:00Z",
        },
    )
    ctx.providers = {
        "stock_media_search": StockMediaProvider(
            pexels_tool=SegmentPexels(api_key="fixture", fixture_mode=True),
            ffmpeg_tool=ffmpeg,
        )
    }
    results = execute_completion_plan([_action("slot-4")], ctx, fail_fast=True, only_aigc=True)
    assert results[0]["ok"] is True
    assert results[0]["stockAttribution"]["segmentCount"] == 3
    assert download_counter["n"] == 3
    assert (generated_root / "slot-4-stock.mp4").is_file()


def test_stock_media_provider_falls_back_to_image_generation(tmp_path: Path) -> None:
    generated_root = tmp_path / "generated"
    generated_root.mkdir()
    png = b"\x89PNG\r\n\x1a\n"
    gateway = MagicMock()
    gateway.generate_image.return_value = png

    class EmptyPexels(PexelsTool):
        def search_photos(self, query: str, *, orientation=None, per_page=15):
            return []

        def search_videos(self, query: str, *, orientation=None, per_page=15):
            return []

    ctx = MaterialContext(
        project_id="project-1",
        generation_id="gen-1",
        render_root=tmp_path / "render",
        generated_root=generated_root,
        gateway=gateway,
        quota=VideoGenQuota(max_slots=0),
        inventory={"userBrief": {"sellingPoints": []}},
        slot_matches=[],
        storyboard=[
            {
                "id": "scene-1",
                "slotId": "slot-usage",
                "startSec": 0.0,
                "endSec": 3.0,
                "visual": "kitchen",
                "script": "hello",
                "source": "generated",
            }
        ],
        structure={
            "slots": [
                {
                    "id": "slot-usage",
                    "role": "usage_scene",
                    "requiredAssetType": ["video"],
                    "scriptIntent": "usage",
                }
            ]
        },
        emit_progress=lambda *_args, **_kwargs: None,
        register_artifact=lambda artifact_type, path: {
            "id": "art-1",
            "type": artifact_type,
            "uri": str(Path(path).resolve()),
            "createdAt": "2026-06-08T00:00:00Z",
        },
    )
    register_default_providers(ctx)
    ctx.providers["stock_media_search"] = StockMediaProvider(pexels_tool=EmptyPexels(fixture_mode=True))
    results = execute_completion_plan([_action("slot-usage")], ctx, fail_fast=True, only_aigc=True)
    assert any(item.get("ok") for item in results)
    assert (generated_root / "slot-usage.png").is_file()
