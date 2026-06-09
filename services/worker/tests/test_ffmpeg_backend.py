from __future__ import annotations

import json
from pathlib import Path

from unittest.mock import patch

import pytest

from app.render.backend import RenderOptions
from app.render.ffmpeg_backend import FfmpegRenderBackend
from app.render.timeline_compiler.compile import compile_timeline_to_mp4
from app.tools.ffmpeg_tool import FFmpegTool


class _FakeResult:
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _ffmpeg_runner(command: list[str]) -> _FakeResult:
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
    output.write_bytes(b"fake-mp4-bytes")
    return _FakeResult()


def _timeline() -> dict:
    return {
        "durationSec": 4,
        "tracks": [
            {
                "id": "video",
                "type": "video",
                "clips": [
                    {
                        "id": "clip-hook",
                        "startSec": 0,
                        "endSec": 4,
                        "sourceRef": "materials/hook.mp4",
                    }
                ],
            },
            {
                "id": "text",
                "type": "text",
                "clips": [
                    {
                        "id": "subtitle-master-1",
                        "startSec": 0,
                        "endSec": 4,
                        "content": "Hello",
                        "styleRef": "style://subtitle/clean",
                    }
                ],
            },
            {
                "id": "vo",
                "type": "voiceover",
                "clips": [
                    {
                        "id": "vo-master",
                        "startSec": 0,
                        "endSec": 4,
                        "sourceRef": "materials/master.wav",
                    }
                ],
            },
        ],
    }


def test_ffmpeg_backend_writes_preview_and_output(tmp_path: Path) -> None:
    storage = tmp_path / "storage"
    project_id = "project-1"
    generation_id = "gen-1"
    render_root = storage / "projects" / project_id / "renders" / generation_id
    materials = render_root / "materials"
    materials.mkdir(parents=True)
    (materials / "hook.mp4").write_bytes(b"v")
    (materials / "master.wav").write_bytes(b"a")

    backend = FfmpegRenderBackend(tool=FFmpegTool(command_runner=_ffmpeg_runner))
    stages: list[str] = []

    def fake_poster_extract(video_path: Path, output_path: Path, **kwargs):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"poster")
        return {"ok": True, "sourceTimeSec": 0.1}

    with patch("app.render.ffmpeg_backend.extract_video_poster", side_effect=fake_poster_extract):
        output = backend.render(
            RenderOptions(
                project_id=project_id,
                generation_id=generation_id,
                timeline=_timeline(),
                storage_root=storage,
                emit_progress=stages.append,
                aspect_ratio="9:16",
            )
        )

    assert output.error is None
    assert (render_root / "preview.html").is_file()
    assert (render_root / "output.mp4").is_file()
    assert (render_root / "poster.jpg").is_file()
    log = json.loads((render_root / "render-log.json").read_text(encoding="utf-8"))
    assert log.get("backend") == "ffmpeg"
    assert "building_timeline" in stages
    assert "compiling_timeline" in stages


def test_compile_timeline_returns_error_when_ffmpeg_missing(tmp_path: Path) -> None:
    def missing_runner(_command: list[str]) -> _FakeResult:
        raise FileNotFoundError("ffmpeg")

    render_root = tmp_path / "render"
    render_root.mkdir()
    result = compile_timeline_to_mp4(
        _timeline(),
        render_root=render_root,
        output_path=render_root / "output.mp4",
        ffmpeg=FFmpegTool(command_runner=missing_runner),
    )
    assert result.ok is False
    assert result.error is not None
