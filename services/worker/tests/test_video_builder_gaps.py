from __future__ import annotations

import json
from pathlib import Path

from app.render.timeline_compiler.scene_segments import SceneSegment, extract_scene_segments
from app.render.timeline_compiler.video_builder import _build_timeline_pieces
from app.tools.ffmpeg_tool import FFmpegTool


class _FakeResult:
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _runner(command: list[str]) -> _FakeResult:
    if command[0] == "ffprobe":
        return _FakeResult(
            stdout=json.dumps(
                {
                    "format": {"duration": "2.0"},
                    "streams": [
                        {
                            "codec_type": "video",
                            "width": 1080,
                            "height": 1920,
                            "avg_frame_rate": "30/1",
                        }
                    ],
                }
            )
        )
    output = Path(command[-1])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(b"v")
    return _FakeResult()


def test_build_timeline_pieces_inserts_gap(tmp_path: Path) -> None:
    render_root = tmp_path / "render"
    materials = render_root / "materials"
    materials.mkdir(parents=True)
    (materials / "a.mp4").write_bytes(b"v")

    timeline = {
        "durationSec": 10,
        "tracks": [
            {
                "id": "video",
                "type": "video",
                "clips": [
                    {
                        "id": "clip-a",
                        "startSec": 0,
                        "endSec": 3,
                        "sourceRef": "materials/a.mp4",
                    },
                    {
                        "id": "clip-b",
                        "startSec": 5,
                        "endSec": 10,
                        "sourceRef": "materials/a.mp4",
                    },
                ],
            }
        ],
    }
    segments = extract_scene_segments(timeline, render_root=render_root)
    ffmpeg = FFmpegTool(command_runner=_runner)
    staging = render_root / "staging"
    built = _build_timeline_pieces(
        ffmpeg,
        segments,
        render_root=render_root,
        staging_dir=staging,
        width=1080,
        height=1920,
        fps=30,
    )
    pieces = built["pieces"]
    assert len(pieces) == 3
    assert pieces[0].is_scene is True
    assert pieces[1].is_scene is False
    assert pieces[1].duration_sec == 2.0
    assert pieces[2].is_scene is True
