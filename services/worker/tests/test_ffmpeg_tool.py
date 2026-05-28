from __future__ import annotations

import json
from pathlib import Path

from app.tools.ffmpeg_tool import FFmpegTool


class _Result:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_probe_extracts_metadata_from_ffprobe_json(tmp_path: Path) -> None:
    def fake_runner(cmd: list[str]) -> _Result:
        assert cmd[0] == "ffprobe"
        payload = {
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": 1920,
                    "height": 1080,
                    "avg_frame_rate": "30000/1001",
                },
                {
                    "codec_type": "audio",
                    "codec_name": "aac",
                },
            ],
            "format": {"duration": "12.5"},
        }
        return _Result(returncode=0, stdout=json.dumps(payload))

    tool = FFmpegTool(command_runner=fake_runner)
    metadata = tool.probe(tmp_path / "video.mp4")

    assert metadata == {
        "durationSec": 12.5,
        "width": 1920,
        "height": 1080,
        "fps": 29.97,
        "videoCodec": "h264",
        "audioCodec": "aac",
        "hasAudio": True,
        "sourcePath": str((tmp_path / "video.mp4").resolve()),
    }


def test_extract_audio_calls_ffmpeg_with_pcm16k_mono(tmp_path: Path) -> None:
    captured: list[list[str]] = []

    def fake_runner(cmd: list[str]) -> _Result:
        captured.append(cmd)
        return _Result(returncode=0)

    output = tmp_path / "audio.wav"
    tool = FFmpegTool(command_runner=fake_runner)
    result = tool.extract_audio(tmp_path / "video.mp4", output)

    assert result["path"] == str(output.resolve())
    assert captured[0][:3] == ["ffmpeg", "-y", "-i"]
    assert "-ar" in captured[0] and "16000" in captured[0]
    assert "-ac" in captured[0] and "1" in captured[0]


def test_missing_ffprobe_returns_retryable_error(tmp_path: Path) -> None:
    def missing_runner(_: list[str]) -> _Result:
        raise FileNotFoundError("ffprobe not found")

    tool = FFmpegTool(command_runner=missing_runner)
    error = tool.probe(tmp_path / "video.mp4")

    assert error["code"] == "ffprobe_missing"
    assert error["retryable"] is True
