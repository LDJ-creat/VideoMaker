from __future__ import annotations

import subprocess
from pathlib import Path

from app.render.timeline_compiler.hold_tail import timeline_target_duration
from app.render.timeline_compiler.scene_segments import SceneSegment
from app.render.timeline_compiler.video_builder import pad_video_to_duration
from app.tools.ffmpeg_tool import FFmpegTool


class _FakeResult:
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _mock_runner_factory(probe_duration: float = 3.0):
    def runner(command: list[str]) -> _FakeResult:
        if command[0] == "ffprobe":
            payload = (
                '{"format":{"duration":"%s"},'
                '"streams":[{"codec_type":"video","width":1080,"height":1920,'
                '"avg_frame_rate":"30/1"}]}'
            ) % probe_duration
            return _FakeResult(stdout=payload)
        output = Path(command[-1])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"fake-video")
        return _FakeResult()

    return runner


def test_timeline_target_duration_prefers_timeline_field() -> None:
    segments = [SceneSegment("a", 0, 5, None, "placeholder")]
    assert timeline_target_duration({"durationSec": 12.0, "tracks": []}, segments) == 12.0


def test_pad_video_to_duration_writes_output(tmp_path: Path) -> None:
    input_path = tmp_path / "in.mp4"
    input_path.write_bytes(b"in")
    output_path = tmp_path / "out.mp4"
    tool = FFmpegTool(command_runner=_mock_runner_factory(probe_duration=3.0))
    result = pad_video_to_duration(tool, input_path, output_path, target_sec=10.0)
    assert "path" in result
    assert Path(result["path"]).is_file()
