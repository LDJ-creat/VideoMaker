from __future__ import annotations

import json
from pathlib import Path

from app.tools.ytdlp_tool import YtDlpTool


class _Result:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_download_url_success_returns_artifact_ready_metadata(tmp_path: Path) -> None:
    def fake_runner(cmd: list[str]) -> _Result:
        if "--dump-json" in cmd:
            return _Result(
                returncode=0,
                stdout=json.dumps(
                    {
                        "duration": 8.0,
                        "ext": "mp4",
                        "filesize": 512000,
                    }
                ),
            )
        if "-o" in cmd:
            output_template = Path(cmd[cmd.index("-o") + 1])
            output_file = output_template.parent / "original.mp4"
            output_file.parent.mkdir(parents=True, exist_ok=True)
            output_file.write_bytes(b"video")
            return _Result(returncode=0)
        raise AssertionError(f"unexpected command: {cmd}")

    tool = YtDlpTool(command_runner=fake_runner)
    result = tool.download("https://example.com/video", tmp_path)

    assert result["ext"] == "mp4"
    assert result["durationSec"] == 8.0
    assert result["sourceUrl"] == "https://example.com/video"
    assert Path(result["path"]).exists()


def test_missing_ytdlp_returns_retryable_error(tmp_path: Path) -> None:
    def fake_runner(_: list[str]) -> _Result:
        raise FileNotFoundError("yt-dlp missing")

    tool = YtDlpTool(command_runner=fake_runner)
    result = tool.download("https://example.com/video", tmp_path)

    assert result["code"] == "ytdlp_missing"
    assert result["retryable"] is True


def test_download_rejects_oversize_video(tmp_path: Path) -> None:
    def fake_runner(cmd: list[str]) -> _Result:
        if "--dump-json" in cmd:
            return _Result(
                returncode=0,
                stdout=json.dumps(
                    {
                        "duration": 10.0,
                        "ext": "mp4",
                        "filesize": 1024 * 1024 * 1024,
                    }
                ),
            )
        raise AssertionError("download should not run when metadata rejects")

    tool = YtDlpTool(command_runner=fake_runner)
    result = tool.download("https://example.com/video", tmp_path, max_file_size_mb=500)

    assert result["code"] == "ytdlp_file_too_large"
    assert result["retryable"] is False


def test_download_passes_cookies_file_to_ytdlp(tmp_path: Path) -> None:
    cookies = tmp_path / "cookies.txt"
    cookies.write_text("# Netscape\n", encoding="utf-8")
    seen: list[list[str]] = []

    def fake_runner(cmd: list[str]) -> _Result:
        seen.append(cmd)
        if "--dump-json" in cmd:
            return _Result(
                returncode=0,
                stdout=json.dumps({"duration": 5.0, "ext": "mp4", "filesize": 1000}),
            )
        output_template = Path(cmd[cmd.index("-o") + 1])
        output_file = output_template.parent / "original.mp4"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_bytes(b"video")
        return _Result(returncode=0)

    tool = YtDlpTool(command_runner=fake_runner)
    tool.download("https://example.com/video", tmp_path / "out", cookies_path=cookies)

    assert seen
    assert "--cookies" in seen[0]
    assert str(cookies.resolve()) in seen[0]


def test_inspect_failure_for_douyin_without_cookie_hint(tmp_path: Path) -> None:
    def fake_runner(_: list[str]) -> _Result:
        return _Result(returncode=1, stderr="ERROR: Unable to extract video data")

    tool = YtDlpTool(command_runner=fake_runner)
    result = tool.download("https://v.douyin.com/example/", tmp_path)

    assert result["code"] == "ytdlp_cookies_required"


def test_inspect_failure_without_cookies_returns_cookies_required(tmp_path: Path) -> None:
    def fake_runner(_: list[str]) -> _Result:
        return _Result(
            returncode=1,
            stderr="ERROR: Fresh cookies (not necessarily logged in) are needed",
        )

    tool = YtDlpTool(command_runner=fake_runner)
    result = tool.download("https://example.com/video", tmp_path)

    assert result["code"] == "ytdlp_cookies_required"
    assert result["retryable"] is True


def test_download_rejects_unsupported_extension(tmp_path: Path) -> None:
    def fake_runner(cmd: list[str]) -> _Result:
        if "--dump-json" in cmd:
            return _Result(
                returncode=0,
                stdout=json.dumps(
                    {
                        "duration": 10.0,
                        "ext": "avi",
                        "filesize": 1024,
                    }
                ),
            )
        raise AssertionError("download should not run when extension rejects")

    tool = YtDlpTool(command_runner=fake_runner)
    result = tool.download("https://example.com/video", tmp_path)

    assert result["code"] == "ytdlp_extension_unsupported"
    assert result["retryable"] is False
