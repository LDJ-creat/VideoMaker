from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.render.render_timeline_to_hyperframes import write_composition


def _load_fixture() -> dict:
    fixture_path = (
        Path(__file__).parent / "fixtures" / "render_timeline.json"
    )
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def test_write_composition_generates_deterministic_outputs(tmp_path: Path) -> None:
    render_root = tmp_path / "render"
    composition_dir = render_root / "composition"
    assets_dir = render_root / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    (assets_dir / "video.mp4").write_text("v", encoding="utf-8")
    (assets_dir / "image.png").write_text("i", encoding="utf-8")

    timeline = _load_fixture()
    write_composition(timeline=timeline, composition_dir=composition_dir, render_root=render_root)

    html = (composition_dir / "index.html").read_text(encoding="utf-8")
    timeline_json = json.loads((composition_dir / "timeline.json").read_text(encoding="utf-8"))

    assert "window.__videomakerSeek" in html
    assert "window.__videomakerTimeline" in html
    assert "Hello &amp; Intro" in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert 'data-track="video"' in html
    assert 'data-start-ms="2500"' in html
    assert "transition-fade" in html
    assert timeline_json["tracks"][0]["type"] == "video"
    assert 'src="../assets/video.mp4"' in html
    assert 'src="../assets/image.png"' in html


def test_write_composition_escapes_script_breakout_in_timeline_json(tmp_path: Path) -> None:
    render_root = tmp_path / "render"
    composition_dir = render_root / "composition"
    timeline = {
        "durationSec": 1,
        "tracks": [
            {
                "id": "text",
                "type": "text",
                "clips": [
                    {
                        "id": "t1",
                        "startSec": 0,
                        "endSec": 1,
                        "content": "</script><script>alert(1)</script>",
                    }
                ],
            }
        ],
    }

    write_composition(timeline=timeline, composition_dir=composition_dir, render_root=render_root)
    html = (composition_dir / "index.html").read_text(encoding="utf-8")

    assert "</script><script>" not in html
    assert "\\u003c/script\\u003e" in html


def test_write_composition_renders_text_track_image_source_ref(tmp_path: Path) -> None:
    render_root = tmp_path / "render"
    composition_dir = render_root / "composition"
    materials_dir = render_root / "materials"
    materials_dir.mkdir(parents=True, exist_ok=True)
    (materials_dir / "slot1.png").write_bytes(b"png")

    timeline = {
        "durationSec": 5,
        "tracks": [
            {
                "id": "track-text",
                "type": "text",
                "clips": [
                    {
                        "id": "clip-slot1",
                        "startSec": 0.0,
                        "endSec": 5.0,
                        "sourceRef": "materials/slot1.png",
                    }
                ],
            }
        ],
    }

    write_composition(timeline=timeline, composition_dir=composition_dir, render_root=render_root)
    html = (composition_dir / "index.html").read_text(encoding="utf-8")
    assert 'class="clip image-clip"' in html
    assert 'src="../materials/slot1.png"' in html


def test_write_composition_rejects_unsafe_source_ref(tmp_path: Path) -> None:
    render_root = tmp_path / "render"
    composition_dir = render_root / "composition"
    timeline = {
        "durationSec": 1,
        "tracks": [
            {
                "id": "v",
                "type": "video",
                "clips": [{"id": "v1", "startSec": 0, "endSec": 1, "sourceRef": "../escape.mp4"}],
            }
        ],
    }

    with pytest.raises(ValueError):
        write_composition(timeline=timeline, composition_dir=composition_dir, render_root=render_root)
