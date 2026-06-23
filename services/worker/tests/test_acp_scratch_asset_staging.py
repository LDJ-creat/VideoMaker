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
    staged = stage_asset_refs_into_scratch(
        [{"type": "video", "uri": str(source)}],
        scratch_dir=scratch,
        generated_root=generated,
    )
    assert staged is not None
    assert staged[0]["uri"] == "slot-1-stock.mp4"
    assert (scratch / "slot-1-stock.mp4").is_file()


def test_prepare_author_request_vm_asset_root_scratch(tmp_path: Path) -> None:
    generated = tmp_path / "generated"
    generated.mkdir()
    video = generated / "clip.mp4"
    video.write_bytes(b"video")
    scratch = tmp_path / "scratch"
    request = prepare_author_request_for_scratch(
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
