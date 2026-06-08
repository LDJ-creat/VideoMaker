from __future__ import annotations

from app.render.timeline_compiler.transition_map import transition_content_at_boundary


def test_transition_content_at_boundary_matches_clip() -> None:
    clips = [
        {"startSec": 3.0, "endSec": 3.18, "content": "fade"},
        {"startSec": 6.0, "endSec": 6.18, "content": "wipe"},
    ]
    assert transition_content_at_boundary(clips, 3.0) == "fade"
    assert transition_content_at_boundary(clips, 6.1) == "wipe"
