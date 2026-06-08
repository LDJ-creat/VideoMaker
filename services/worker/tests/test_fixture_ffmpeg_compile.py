from __future__ import annotations

import json
from pathlib import Path

from app.render.timeline_compiler.compile import compile_timeline_to_mp4
from app.tools.ffmpeg_tool import FFmpegTool, build_fixture_ffmpeg_tool


class _FakeResult:
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_fixture_ffmpeg_tool_builds_output(tmp_path: Path) -> None:
    render_root = tmp_path / "render"
    materials = render_root / "materials"
    materials.mkdir(parents=True)
    (materials / "hook.mp4").write_bytes(b"v")
    (materials / "master.wav").write_bytes(b"a")

    timeline = {
        "durationSec": 2,
        "tracks": [
            {
                "id": "video",
                "type": "video",
                "clips": [
                    {
                        "id": "clip-hook",
                        "startSec": 0,
                        "endSec": 2,
                        "sourceRef": "materials/hook.mp4",
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
                        "endSec": 2,
                        "sourceRef": "materials/master.wav",
                    }
                ],
            },
        ],
    }

    result = compile_timeline_to_mp4(
        timeline,
        render_root=render_root,
        output_path=render_root / "output.mp4",
        ffmpeg=build_fixture_ffmpeg_tool(),
        tts_mode="global",
    )
    assert result.ok, result.error
    assert (render_root / "output.mp4").is_file()


def test_compile_fails_when_subtitle_burn_fails(tmp_path: Path) -> None:
    render_root = tmp_path / "render"
    materials = render_root / "materials"
    materials.mkdir(parents=True)
    (materials / "hook.mp4").write_bytes(b"v")

    def _fail_ass_runner(command: list[str]) -> _FakeResult:
        if "-vf" in command and any("ass=" in part for part in command):
            return _FakeResult(returncode=1, stderr="ass failed")
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
        output.write_bytes(b"x")
        return _FakeResult()

    timeline = {
        "durationSec": 2,
        "tracks": [
            {
                "id": "video",
                "type": "video",
                "clips": [
                    {
                        "id": "clip-hook",
                        "startSec": 0,
                        "endSec": 2,
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
                        "endSec": 2,
                        "content": "fail",
                        "styleRef": "style://subtitle/clean",
                    }
                ],
            },
        ],
    }

    result = compile_timeline_to_mp4(
        timeline,
        render_root=render_root,
        output_path=render_root / "output.mp4",
        ffmpeg=FFmpegTool(command_runner=_fail_ass_runner),
    )
    assert result.ok is False
    assert result.log.get("status") == "failed"
    assert result.error is not None
