from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

CommandRunner = Callable[[list[str]], Any]
ALLOWED_EXTENSIONS = {"mp4", "mov", "mkv", "webm"}


def _tool_error(
    code: str,
    message: str,
    *,
    retryable: bool,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "retryable": retryable,
        "details": details or {},
    }


def _with_cookies(command: list[str], cookies_path: str | Path | None) -> list[str]:
    if not cookies_path:
        return command
    path = Path(cookies_path)
    if not path.is_file():
        return command
    return [command[0], "--cookies", str(path.resolve()), *command[1:]]


def _platform_from_url(url: str) -> str | None:
    host = (urlparse(url).hostname or "").lower()
    if not host:
        return None
    if "douyin" in host:
        return "douyin"
    if "bilibili" in host or host == "b23.tv":
        return "bilibili"
    if "youtube" in host or host == "youtu.be":
        return "youtube"
    return None


def _classify_ytdlp_failure(stderr: str, url: str = "") -> tuple[str, str]:
    lowered = stderr.lower()
    url_lower = url.lower()
    cookie_signals = (
        "cookie" in lowered
        and any(
            token in lowered
            for token in (
                "needed",
                "required",
                "fresh",
                "login",
                "sign in",
                "sign-in",
                "expired",
                "invalid",
                "no longer",
            )
        )
    ) or any(
        phrase in lowered
        for phrase in (
            "fresh cookies",
            "pass cookies",
            "use --cookies",
            "cookies from browser",
        )
    )
    if cookie_signals:
        return (
            "ytdlp_cookies_required",
            "Platform requires browser cookies for this URL",
        )
    if any(host in url_lower for host in ("douyin.com", "iesdouyin.com", "bilibili.com", "b23.tv")):
        if "unsupported url" not in lowered:
            return (
                "ytdlp_cookies_required",
                "This platform likely requires browser cookies for this URL",
            )
    if "unsupported url" in lowered or "unsupported error" in lowered:
        return ("ytdlp_unsupported_url", "yt-dlp cannot inspect this URL")
    return ("ytdlp_unsupported_url", "yt-dlp cannot inspect this URL")


class YtDlpTool:
    def __init__(self, command_runner: CommandRunner | None = None) -> None:
        self._command_runner = command_runner or self._default_runner

    @staticmethod
    def _default_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(command, capture_output=True, text=True, check=False)

    def download(
        self,
        url: str,
        output_dir: str | Path,
        *,
        cookies_path: str | Path | None = None,
        max_duration_sec: int = 180,
        max_file_size_mb: int = 500,
    ) -> dict[str, Any]:
        output_root = Path(output_dir).resolve()
        output_root.mkdir(parents=True, exist_ok=True)

        metadata = self._inspect_url(url, cookies_path=cookies_path)
        if "code" in metadata:
            return metadata

        duration_sec = float(metadata.get("duration") or 0.0)
        ext = str(metadata.get("ext") or "").lower()
        file_size = int(metadata.get("filesize") or metadata.get("filesize_approx") or 0)

        if duration_sec and duration_sec > max_duration_sec:
            return _tool_error(
                "ytdlp_duration_exceeded",
                "video duration exceeds allowed maximum",
                retryable=False,
                details={"durationSec": duration_sec, "maxDurationSec": max_duration_sec},
            )
        if ext and ext not in ALLOWED_EXTENSIONS:
            return _tool_error(
                "ytdlp_extension_unsupported",
                "video extension is not supported",
                retryable=False,
                details={"ext": ext, "allowed": sorted(ALLOWED_EXTENSIONS)},
            )
        if file_size and file_size > max_file_size_mb * 1024 * 1024:
            return _tool_error(
                "ytdlp_file_too_large",
                "video file size exceeds allowed maximum",
                retryable=False,
                details={"filesize": file_size, "maxFileSizeMb": max_file_size_mb},
            )

        output_template = output_root / "original.%(ext)s"
        download_command = _with_cookies(
            [
                "yt-dlp",
                url,
                "-o",
                str(output_template),
                "--no-playlist",
            ],
            cookies_path,
        )
        try:
            result = self._command_runner(download_command)
        except FileNotFoundError:
            return _tool_error("ytdlp_missing", "yt-dlp is not installed", retryable=True)

        if result.returncode != 0:
            code, message = _classify_ytdlp_failure(result.stderr or "", url)
            if code == "ytdlp_unsupported_url":
                code, message = "ytdlp_download_failed", "yt-dlp failed to download the URL"
            platform = _platform_from_url(url)
            return _tool_error(
                code,
                message,
                retryable=code == "ytdlp_cookies_required",
                details={"stderr": result.stderr, "platform": platform, "url": url},
            )

        resolved_file = self._resolve_downloaded_file(output_root, ext)
        if resolved_file is None:
            return _tool_error(
                "ytdlp_output_missing",
                "yt-dlp finished without an output file",
                retryable=True,
            )

        return {
            "path": str(resolved_file),
            "durationSec": duration_sec,
            "ext": resolved_file.suffix.lstrip(".").lower(),
            "sourceUrl": url,
        }

    def _inspect_url(
        self,
        url: str,
        *,
        cookies_path: str | Path | None = None,
    ) -> dict[str, Any]:
        inspect_command = _with_cookies(
            ["yt-dlp", "--dump-json", "--no-playlist", url],
            cookies_path,
        )
        try:
            result = self._command_runner(inspect_command)
        except FileNotFoundError:
            return _tool_error("ytdlp_missing", "yt-dlp is not installed", retryable=True)

        if result.returncode != 0:
            stderr = result.stderr or ""
            code, message = _classify_ytdlp_failure(stderr, url)
            platform = _platform_from_url(url)
            return _tool_error(
                code,
                message,
                retryable=code == "ytdlp_cookies_required",
                details={"stderr": stderr, "platform": platform, "url": url},
            )

        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return _tool_error(
                "ytdlp_metadata_parse_failed",
                "yt-dlp metadata is invalid JSON",
                retryable=False,
            )

    @staticmethod
    def _resolve_downloaded_file(output_dir: Path, preferred_ext: str) -> Path | None:
        if preferred_ext:
            preferred = output_dir / f"original.{preferred_ext}"
            if preferred.exists():
                return preferred.resolve()
        candidates = sorted(output_dir.glob("original.*"), key=lambda p: p.stat().st_mtime, reverse=True)
        return candidates[0].resolve() if candidates else None
