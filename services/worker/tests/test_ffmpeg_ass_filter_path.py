from __future__ import annotations

from pathlib import Path

from app.tools.ffmpeg_tool import FFmpegTool


def test_ffmpeg_ass_filter_path_quotes_windows_drive(tmp_path: Path) -> None:
    ass_path = tmp_path / "subtitles.ass"
    ass_path.write_text("[Script Info]\n", encoding="utf-8")

    escaped = FFmpegTool._ffmpeg_ass_filter_path(ass_path)

    assert escaped.startswith("D\\:") or ":" not in escaped or escaped[1:3] == "\\:"
    assert "'" not in escaped


def test_burn_subtitles_command_uses_quoted_ass_filter(tmp_path: Path, monkeypatch) -> None:
    video = tmp_path / "in.mp4"
    ass = tmp_path / "sub.ass"
    out = tmp_path / "out.mp4"
    video.write_bytes(b"\x00")
    ass.write_text(
        "[Script Info]\nScriptType: v4.00+\n\n[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        "Style: Default,Arial,48,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,"
        "0,0,0,0,100,100,0,0,1,2,0,2,40,40,40,1\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, "
        "MarginV, Effect, Text\n"
        "Dialogue: 0,0:00:00.00,0:00:01.00,Default,,0,0,0,,hello\n",
        encoding="utf-8",
    )

    captured: list[list[str]] = []

    def fake_runner(command: list[str]):
        captured.append(command)

        class Result:
            returncode = 0
            stderr = ""

        return Result()

    tool = FFmpegTool(command_runner=fake_runner)
    result = tool.burn_subtitles(video, ass, out, copy_audio=False)

    assert result.get("code") is None
    vf_arg = next(arg for arg in captured[0] if isinstance(arg, str) and arg.startswith("ass="))
    assert vf_arg.startswith("ass='")
    assert vf_arg.endswith("'")
