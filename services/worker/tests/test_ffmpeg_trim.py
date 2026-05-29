from pathlib import Path

from app.tools.ffmpeg_tool import FFmpegTool


def test_trim_clip_returns_path_on_success(tmp_path: Path) -> None:
    source = tmp_path / "source.mp4"
    source.write_bytes(b"not-a-real-mp4-but-ok-for-mock")
    output = tmp_path / "clip.mp4"

    def runner(command: list[str]) -> object:
        output.write_bytes(b"trimmed")
        return type("Result", (), {"returncode": 0, "stderr": ""})()

    tool = FFmpegTool(command_runner=runner)
    result = tool.trim_clip(source, output, start_sec=0.0, duration_sec=2.0)

    assert result.get("path") == str(output.resolve())
    assert output.is_file()
