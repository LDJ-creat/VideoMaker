from __future__ import annotations

from pathlib import Path

from composition.build.media_staging import (
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
