from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Callable

CommandRunner = Callable[[list[str]], Any]


def _retryable_tool_error(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "retryable": True,
        "details": details or {},
    }


class FFmpegTool:
    def __init__(self, command_runner: CommandRunner | None = None) -> None:
        self._command_runner = command_runner or self._default_runner

    @staticmethod
    def _default_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )

    def probe(self, video_path: str | Path) -> dict[str, Any]:
        resolved_path = Path(video_path).resolve()
        command = [
            "ffprobe",
            "-v",
            "error",
            "-show_format",
            "-show_streams",
            "-print_format",
            "json",
            str(resolved_path),
        ]
        try:
            result = self._command_runner(command)
        except FileNotFoundError:
            return _retryable_tool_error("ffprobe_missing", "ffprobe is not installed")

        if result.returncode != 0:
            return _retryable_tool_error(
                "ffprobe_failed",
                "ffprobe execution failed",
                {"stderr": result.stderr},
            )

        try:
            payload = json.loads(result.stdout or "{}")
        except json.JSONDecodeError:
            return {
                "code": "ffprobe_output_invalid",
                "message": "ffprobe returned invalid JSON",
                "retryable": False,
                "details": {"stdout": result.stdout},
            }
        streams = payload.get("streams", [])
        format_payload = payload.get("format", {})
        video_stream = next((s for s in streams if s.get("codec_type") == "video"), {})
        audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

        try:
            fps_value = self._parse_fps(video_stream.get("avg_frame_rate", "0/1"))
            return {
                "durationSec": float(format_payload.get("duration", 0.0)),
                "width": int(video_stream.get("width", 0)),
                "height": int(video_stream.get("height", 0)),
                "fps": round(fps_value, 2),
                "videoCodec": video_stream.get("codec_name"),
                "audioCodec": audio_stream.get("codec_name") if audio_stream else None,
                "hasAudio": audio_stream is not None,
                "sourcePath": str(resolved_path),
            }
        except (TypeError, ValueError, ZeroDivisionError) as exc:
            return {
                "code": "ffprobe_metadata_invalid",
                "message": "ffprobe metadata fields are invalid",
                "retryable": False,
                "details": {"error": str(exc)},
            }

    def extract_audio(self, video_path: str | Path, output_path: str | Path) -> dict[str, Any]:
        resolved_input = Path(video_path).resolve()
        resolved_output = Path(output_path).resolve()
        resolved_output.parent.mkdir(parents=True, exist_ok=True)
        command = [
            "ffmpeg",
            "-y",
            "-i",
            str(resolved_input),
            "-vn",
            "-acodec",
            "pcm_s16le",
            "-ar",
            "16000",
            "-ac",
            "1",
            str(resolved_output),
        ]
        try:
            result = self._command_runner(command)
        except FileNotFoundError:
            return _retryable_tool_error("ffmpeg_missing", "ffmpeg is not installed")

        if result.returncode != 0:
            return _retryable_tool_error(
                "ffmpeg_extract_audio_failed",
                "ffmpeg audio extraction failed",
                {"stderr": result.stderr},
            )
        return {"path": str(resolved_output)}

    def trim_clip(
        self,
        video_path: str | Path,
        output_path: str | Path,
        *,
        start_sec: float,
        duration_sec: float,
    ) -> dict[str, Any]:
        resolved_input = Path(video_path).resolve()
        resolved_output = Path(output_path).resolve()
        resolved_output.parent.mkdir(parents=True, exist_ok=True)
        duration = max(0.1, float(duration_sec))
        start = max(0.0, float(start_sec))

        copy_command = [
            "ffmpeg",
            "-y",
            "-ss",
            str(start),
            "-i",
            str(resolved_input),
            "-t",
            str(duration),
            "-c",
            "copy",
            str(resolved_output),
        ]
        try:
            copy_result = self._command_runner(copy_command)
        except FileNotFoundError:
            return _retryable_tool_error("ffmpeg_missing", "ffmpeg is not installed")

        if copy_result.returncode == 0 and resolved_output.is_file() and resolved_output.stat().st_size > 0:
            return {"path": str(resolved_output)}

        reencode_command = [
            "ffmpeg",
            "-y",
            "-ss",
            str(start),
            "-i",
            str(resolved_input),
            "-t",
            str(duration),
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            str(resolved_output),
        ]
        try:
            reencode_result = self._command_runner(reencode_command)
        except FileNotFoundError:
            return _retryable_tool_error("ffmpeg_missing", "ffmpeg is not installed")

        if reencode_result.returncode != 0:
            return _retryable_tool_error(
                "ffmpeg_trim_failed",
                "ffmpeg trim failed",
                {
                    "stderr": reencode_result.stderr or copy_result.stderr,
                },
            )
        if not resolved_output.is_file() or resolved_output.stat().st_size == 0:
            return {
                "code": "ffmpeg_trim_empty_output",
                "message": "ffmpeg trim produced no output",
                "retryable": True,
                "details": {},
            }
        return {"path": str(resolved_output)}

    def still_image_to_video(
        self,
        image_path: str | Path,
        output_path: str | Path,
        *,
        duration_sec: float,
        fps: int = 30,
    ) -> dict[str, Any]:
        """Turn a still image into an H.264 clip of the requested duration."""
        resolved_input = Path(image_path).resolve()
        resolved_output = Path(output_path).resolve()
        resolved_output.parent.mkdir(parents=True, exist_ok=True)
        duration = max(0.1, float(duration_sec))
        command = [
            "ffmpeg",
            "-y",
            "-loop",
            "1",
            "-i",
            str(resolved_input),
            "-t",
            str(duration),
            "-vf",
            f"fps={max(1, int(fps))},scale=trunc(iw/2)*2:trunc(ih/2)*2",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-an",
            str(resolved_output),
        ]
        try:
            result = self._command_runner(command)
        except FileNotFoundError:
            return _retryable_tool_error("ffmpeg_missing", "ffmpeg is not installed")

        if result.returncode != 0:
            return _retryable_tool_error(
                "ffmpeg_image_to_video_failed",
                "ffmpeg could not build video from still image",
                {"stderr": result.stderr},
            )
        if not resolved_output.is_file() or resolved_output.stat().st_size == 0:
            return {
                "code": "ffmpeg_image_to_video_empty_output",
                "message": "ffmpeg produced no output for still image",
                "retryable": True,
                "details": {},
            }
        return {"path": str(resolved_output)}

    @staticmethod
    def _parse_fps(raw_fps: str) -> float:
        if "/" in raw_fps:
            numerator, denominator = raw_fps.split("/", maxsplit=1)
            denominator_value = float(denominator) if float(denominator) != 0 else 1.0
            return float(numerator) / denominator_value
        return float(raw_fps)
