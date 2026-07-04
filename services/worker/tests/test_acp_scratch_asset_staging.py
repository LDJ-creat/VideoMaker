from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.composition.acp.scratch_assets import (
    list_scratch_media,
    prepare_author_request_for_scratch,
    stage_asset_refs_into_scratch,
)
from composition.types import AuthorRequest


def test_stage_asset_refs_uses_basename(tmp_path: Path) -> None:
    generated = tmp_path / "generated"
    generated.mkdir()
    source = generated / "slot-1-stock.mp4"
    source.write_bytes(b"video-bytes")
    scratch = tmp_path / "scratch"
    staged, _diag = stage_asset_refs_into_scratch(
        [{"type": "video", "uri": str(source)}],
        scratch_dir=scratch,
        generated_root=generated,
    )
    assert staged is not None
    assert staged[0]["uri"] == "slot-1-stock.mp4"
    assert (scratch / "slot-1-stock.mp4").is_file()


def test_prepare_author_request_normalizes_sparse_video_for_source_then_polish(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.composition.acp import scratch_assets as scratch_module
    from app.composition.acp.base_video_normalize import BaseVideoDiagnostics

    generated = tmp_path / "generated"
    generated.mkdir()
    video = generated / "slot-5-stock.mp4"
    video.write_bytes(b"video")
    scratch = tmp_path / "scratch"

    def fake_prepare(src: Path, scratch_dir: Path, **kwargs: object) -> tuple[Path, BaseVideoDiagnostics]:
        scratch_dir.mkdir(parents=True, exist_ok=True)
        dest = scratch_dir / "slot-5-stock-normalized.mp4"
        dest.write_bytes(b"normalized")
        return dest, BaseVideoDiagnostics(max_keyframe_interval_sec=8.33, reencoded=True)

    monkeypatch.setattr(scratch_module, "prepare_base_video_for_scratch", fake_prepare)

    request, diagnostics = prepare_author_request_for_scratch(
        AuthorRequest(
            project_id="p1",
            slot={"role": "benefit_card"},
            asset_refs=[{"type": "video", "uri": str(video)}],
            aspect_ratio="9:16",
            finish_brief={"completionMode": "source_then_polish"},
        ),
        scratch_dir=scratch,
        generated_root=generated,
    )
    assert request.asset_refs is not None
    assert request.asset_refs[0]["uri"] == "slot-5-stock-normalized.mp4"
    assert diagnostics is not None
    assert diagnostics["reencoded"] is True


def test_prepare_author_request_vm_asset_root_scratch(tmp_path: Path) -> None:
    generated = tmp_path / "generated"
    generated.mkdir()
    video = generated / "clip.mp4"
    video.write_bytes(b"video")
    scratch = tmp_path / "scratch"
    request, _diagnostics = prepare_author_request_for_scratch(
        AuthorRequest(
            project_id="p1",
            slot={"role": "hook_visual"},
            asset_refs=[{"type": "video", "uri": "clip.mp4"}],
            aspect_ratio="9:16",
        ),
        scratch_dir=scratch,
        generated_root=generated,
    )
    assert request.asset_refs is not None
    assert request.asset_refs[0]["uri"] == "clip.mp4"
    assert list_scratch_media(scratch) == ["clip.mp4"]
