from __future__ import annotations

from pathlib import Path

from app.render.timeline_compiler.hold_tail import apply_hold_tail_to_segments
from app.render.timeline_compiler.scene_segments import (
    SceneSegment,
    extract_scene_segments,
    normalize_non_overlapping_segments,
)


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


def test_normalize_non_overlapping_segments_clamps_overlap_and_target() -> None:
    """Regression: d6b59479-style overlap must sequentialize within audio target."""
    segments = [
        SceneSegment("clip-1", 0.0, 5.0, "a.mp4", "video"),
        SceneSegment("clip-2", 4.0, 10.0, "b.mp4", "video"),
        SceneSegment("clip-3", 9.0, 12.0, "c.mp4", "video"),
        SceneSegment("clip-4", 11.0, 15.0, "d.mp4", "video"),
        SceneSegment("clip-5", 14.0, 32.895, "e.mp4", "video"),
        SceneSegment("clip-6", 30.8, 35.0, "f.mp4", "video"),
    ]
    normalized = normalize_non_overlapping_segments(segments, 30.8)
    # slot-6 started at 30.8s (audio end) with zero window — dropped until P0.2 ripple fixes storyboard
    assert len(normalized) == 5
    cursor = 0.0
    total = 0.0
    for segment in normalized:
        assert segment.start_sec >= cursor - 0.001
        assert segment.end_sec <= 30.8 + 0.001
        duration = segment.end_sec - segment.start_sec
        assert duration >= 0.05
        total += duration
        cursor = segment.end_sec
    assert abs(total - 30.8) <= 0.15
    assert normalized[-1].end_sec <= 30.8 + 0.001
