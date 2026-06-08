from __future__ import annotations

from pathlib import Path

from app.render.timeline_compiler.hold_tail import apply_hold_tail_to_segments
from app.render.timeline_compiler.scene_segments import SceneSegment, extract_scene_segments


def test_extract_scene_segments_from_video_and_image(tmp_path: Path) -> None:
    render_root = tmp_path / "render"
    assets = render_root / "materials"
    assets.mkdir(parents=True)
    (assets / "slot-a.mp4").write_bytes(b"mp4")
    (assets / "slot-b.png").write_bytes(b"png")

    timeline = {
        "durationSec": 6,
        "tracks": [
            {
                "id": "vid",
                "type": "video",
                "clips": [
                    {
                        "id": "clip-hook",
                        "startSec": 0,
                        "endSec": 3,
                        "sourceRef": "materials/slot-a.mp4",
                    }
                ],
            },
            {
                "id": "img",
                "type": "image",
                "clips": [
                    {
                        "id": "clip-benefit",
                        "startSec": 3,
                        "endSec": 6,
                        "sourceRef": "materials/slot-b.png",
                    }
                ],
            },
        ],
    }

    segments = extract_scene_segments(timeline, render_root=render_root)
    assert len(segments) == 2
    assert segments[0].clip_id == "clip-hook"
    assert segments[0].media_kind == "video"
    assert segments[1].media_kind == "image"


def test_apply_hold_tail_extends_last_segment() -> None:
    segments = [
        SceneSegment("clip-a", 0.0, 3.0, None, "placeholder"),
        SceneSegment("clip-b", 3.0, 6.0, None, "placeholder"),
    ]
    updated = apply_hold_tail_to_segments(segments, 10.0)
    assert updated[-1].end_sec == 10.0
    assert updated[-1].duration_sec == 7.0
