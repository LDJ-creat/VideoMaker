from __future__ import annotations

from pathlib import Path

import pytest

from composition.build.media_staging import (
    MediaStagingError,
    ensure_base_video_aliases_in_asset_root,
    normalize_and_stage_composition_media,
    normalize_video_tags_for_lint,
)


def test_normalize_video_tags_adds_muted_for_data_start() -> None:
    html = (
        '<video id="base-video" class="absolute inset-0 h-full w-full object-cover" '
        'src="slot-3-stock.mp4" data-start="0" data-duration="3"></video>'
    )
    normalized = normalize_video_tags_for_lint(html)
    assert ' muted' in normalized or normalized.startswith('<video muted')
    assert "playsinline" in normalized


def test_normalize_video_tags_preserves_audible_video() -> None:
    html = (
        '<video id="base-video" src="clip.mp4" data-start="0" '
        'data-has-audio="true"></video>'
    )
    normalized = normalize_video_tags_for_lint(html)
    assert " muted" not in normalized
    assert 'data-has-audio="true"' in normalized


def test_normalize_and_stage_copies_stock_video_into_composition(tmp_path: Path) -> None:
    generated = tmp_path / "generated"
    generated.mkdir()
    stock = generated / "slot-3-stock.mp4"
    stock.write_bytes(b"x" * 128)

    composition_dir = generated / "action-slot-3-finish" / "composition"
    composition_dir.mkdir(parents=True)
    html = (
        '<video src="slot-3-stock.mp4" muted playsinline></video>'
    )
    normalized = normalize_and_stage_composition_media(
        composition_dir,
        asset_root=generated,
        html=html,
    )
    staged = composition_dir / "slot-3-stock.mp4"
    assert staged.is_file()
    assert staged.stat().st_size == 128
    assert 'src="slot-3-stock.mp4"' in normalized


def test_normalize_and_stage_strips_unresolved_placeholder_video(tmp_path: Path) -> None:
    composition_dir = tmp_path / "composition"
    composition_dir.mkdir()
    html = (
        '<div><video src="{{asset_root}}scene_demo.mp4" muted></video>'
        '<p id="keep">ok</p></div>'
    )
    normalized = normalize_and_stage_composition_media(
        composition_dir,
        asset_root=None,
        html=html,
    )
    assert "<video" not in normalized
    assert 'id="keep"' in normalized


def test_normalize_and_stage_resolves_normalized_src_from_stock_basename(tmp_path: Path) -> None:
    generated = tmp_path / "generated"
    generated.mkdir()
    stock = generated / "slot-1-stock.mp4"
    stock.write_bytes(b"x" * 128)

    composition_dir = generated / "action-slot-1-finish" / "composition"
    composition_dir.mkdir(parents=True)
    html = (
        '<video id="base-video" src="slot-1-stock-normalized.mp4" muted playsinline></video>'
    )
    normalized = normalize_and_stage_composition_media(
        composition_dir,
        asset_root=generated,
        html=html,
    )
    staged = composition_dir / "slot-1-stock-normalized.mp4"
    assert staged.is_file()
    assert staged.stat().st_size == 128
    assert 'src="slot-1-stock-normalized.mp4"' in normalized
    assert "<video" in normalized


def test_normalize_and_stage_raises_when_base_video_missing_with_asset_root(tmp_path: Path) -> None:
    generated = tmp_path / "generated"
    generated.mkdir()
    composition_dir = generated / "composition"
    composition_dir.mkdir(parents=True)
    html = '<video src="slot-1-stock-normalized.mp4" muted></video>'
    with pytest.raises(MediaStagingError, match="slot-1-stock-normalized.mp4"):
        normalize_and_stage_composition_media(
            composition_dir,
            asset_root=generated,
            html=html,
        )


def test_ensure_base_video_aliases_in_asset_root(tmp_path: Path) -> None:
    generated = tmp_path / "generated"
    generated.mkdir()
    stock = generated / "slot-1-stock.mp4"
    stock.write_bytes(b"stock")

    ensure_base_video_aliases_in_asset_root(
        '<video src="slot-1-stock-normalized.mp4"></video>',
        generated,
    )

    alias = generated / "slot-1-stock-normalized.mp4"
    assert alias.is_file()
    assert alias.read_bytes() == b"stock"
