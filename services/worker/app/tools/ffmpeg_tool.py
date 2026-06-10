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

    @staticmethod
    def _parse_fps(raw_fps: str) -> float:
        if "/" in raw_fps:
            numerator, denominator = raw_fps.split("/", maxsplit=1)
            denominator_value = float(denominator) if float(denominator) != 0 else 1.0
            return float(numerator) / denominator_value
        return float(raw_fps)

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

    def concat_clips(
        self,
        clip_paths: list[str | Path],
        output_path: str | Path,
    ) -> dict[str, Any]:
        """Concatenate homogenous H.264/AAC clips via ffmpeg concat demuxer."""
        inputs = [Path(path).resolve() for path in clip_paths]
        if not inputs:
            return {
                "code": "ffmpeg_concat_empty",
                "message": "No clips provided for concat",
                "retryable": False,
                "details": {},
            }
        resolved_output = Path(output_path).resolve()
        resolved_output.parent.mkdir(parents=True, exist_ok=True)
        if len(inputs) == 1:
            resolved_output.write_bytes(inputs[0].read_bytes())
            return {"path": str(resolved_output)}

        list_path = resolved_output.parent / f"{resolved_output.stem}-concat-list.txt"
        lines = [f"file '{path.as_posix()}'" for path in inputs]
        list_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        copy_command = [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_path),
            "-c",
            "copy",
            str(resolved_output),
        ]
        try:
            copy_result = self._command_runner(copy_command)
        except FileNotFoundError:
            return _retryable_tool_error("ffmpeg_missing", "ffmpeg is not installed")

        if copy_result.returncode == 0 and resolved_output.is_file() and resolved_output.stat().st_size > 0:
            list_path.unlink(missing_ok=True)
            return {"path": str(resolved_output)}

        reencode_command = [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_path),
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
        finally:
            list_path.unlink(missing_ok=True)

        if reencode_result.returncode != 0:
            return _retryable_tool_error(
                "ffmpeg_concat_failed",
                "ffmpeg concat failed",
                {"stderr": reencode_result.stderr or copy_result.stderr},
            )
        if not resolved_output.is_file() or resolved_output.stat().st_size == 0:
            return {
                "code": "ffmpeg_concat_empty_output",
                "message": "ffmpeg concat produced no output",
                "retryable": True,
                "details": {},
            }
        return {"path": str(resolved_output)}

    def scale_pad_video(
        self,
        input_path: str | Path,
        output_path: str | Path,
        *,
        width: int,
        height: int,
        fps: int = 30,
    ) -> dict[str, Any]:
        resolved_input = Path(input_path).resolve()
        resolved_output = Path(output_path).resolve()
        resolved_output.parent.mkdir(parents=True, exist_ok=True)
        vf = (
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={max(1, int(fps))}"
        )
        command = [
            "ffmpeg",
            "-y",
            "-i",
            str(resolved_input),
            "-vf",
            vf,
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
                "ffmpeg_scale_pad_failed",
                "ffmpeg scale/pad failed",
                {"stderr": result.stderr},
            )
        if not resolved_output.is_file() or resolved_output.stat().st_size == 0:
            return {
                "code": "ffmpeg_scale_pad_empty_output",
                "message": "ffmpeg scale/pad produced no output",
                "retryable": True,
                "details": {},
            }
        return {"path": str(resolved_output)}

    def color_video(
        self,
        output_path: str | Path,
        *,
        duration_sec: float,
        width: int,
        height: int,
        fps: int = 30,
        color: str = "black",
    ) -> dict[str, Any]:
        resolved_output = Path(output_path).resolve()
        resolved_output.parent.mkdir(parents=True, exist_ok=True)
        duration = max(0.1, float(duration_sec))
        command = [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c={color}:s={width}x{height}:d={duration}:r={max(1, int(fps))}",
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
                "ffmpeg_color_video_failed",
                "ffmpeg color video failed",
                {"stderr": result.stderr},
            )
        return {"path": str(resolved_output)}

    def pad_video_duration(
        self,
        input_path: str | Path,
        output_path: str | Path,
        *,
        target_sec: float,
    ) -> dict[str, Any]:
        resolved_input = Path(input_path).resolve()
        resolved_output = Path(output_path).resolve()
        resolved_output.parent.mkdir(parents=True, exist_ok=True)
        target = max(0.1, float(target_sec))
        probe = self.probe(resolved_input)
        if probe.get("code"):
            return probe
        current = float(probe.get("durationSec") or 0.0)
        if current >= target - 0.05:
            if resolved_input != resolved_output:
                resolved_output.write_bytes(resolved_input.read_bytes())
            return {"path": str(resolved_output)}

        pad_sec = max(0.0, target - current)
        command = [
            "ffmpeg",
            "-y",
            "-i",
            str(resolved_input),
            "-vf",
            f"tpad=stop_mode=clone:stop_duration={pad_sec}",
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
                "ffmpeg_pad_duration_failed",
                "ffmpeg pad duration failed",
                {"stderr": result.stderr},
            )
        return {"path": str(resolved_output)}

    def run_filter_complex(
        self,
        *,
        inputs: list[str | Path],
        filter_graph: str,
        output_path: str | Path,
        maps: list[str] | None = None,
        extra_args: list[str] | None = None,
    ) -> dict[str, Any]:
        resolved_output = Path(output_path).resolve()
        resolved_output.parent.mkdir(parents=True, exist_ok=True)
        command: list[str] = ["ffmpeg", "-y"]
        for item in inputs:
            command.extend(["-i", str(Path(item).resolve())])
        command.extend(["-filter_complex", filter_graph])
        for mapping in maps or ["-map", "[outv]"]:
            if mapping.startswith("-"):
                command.append(mapping)
            else:
                command.extend(["-map", mapping])
        if extra_args:
            command.extend(extra_args)
        command.append(str(resolved_output))
        try:
            result = self._command_runner(command)
        except FileNotFoundError:
            return _retryable_tool_error("ffmpeg_missing", "ffmpeg is not installed")
        if result.returncode != 0:
            return _retryable_tool_error(
                "ffmpeg_filter_complex_failed",
                "ffmpeg filter_complex failed",
                {"stderr": result.stderr},
            )
        if not resolved_output.is_file() or resolved_output.stat().st_size == 0:
            return {
                "code": "ffmpeg_filter_complex_empty_output",
                "message": "ffmpeg filter_complex produced no output",
                "retryable": True,
                "details": {},
            }
        return {"path": str(resolved_output)}

    @staticmethod
    def _ffmpeg_ass_filter_path(path: Path) -> str:
        """Escape ASS path for ffmpeg ass= filter (Windows drive-safe, quoted)."""
        posix = path.resolve().as_posix()
        if len(posix) > 1 and posix[1] == ":":
            escaped = posix[0] + "\\:" + posix[2:]
        else:
            escaped = posix
        return escaped.replace("'", "\\'")

    def burn_subtitles(
        self,
        video_path: str | Path,
        ass_path: str | Path,
        output_path: str | Path,
        *,
        copy_audio: bool = True,
    ) -> dict[str, Any]:
        resolved_video = Path(video_path).resolve()
        resolved_ass = Path(ass_path).resolve()
        resolved_output = Path(output_path).resolve()
        resolved_output.parent.mkdir(parents=True, exist_ok=True)
        # Co-locate ASS beside output to avoid Windows drive-colon filter issues.
        local_ass = resolved_output.parent / "_render_subtitles.ass"
        if resolved_ass != local_ass:
            local_ass.write_bytes(resolved_ass.read_bytes())
        ass_filter = self._ffmpeg_ass_filter_path(local_ass)
        command = [
            "ffmpeg",
            "-y",
            "-i",
            str(resolved_video),
            "-vf",
            f"ass='{ass_filter}'",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
        ]
        if copy_audio:
            command.extend(["-c:a", "copy"])
        else:
            command.append("-an")
        command.append(str(resolved_output))
        try:
            result = self._command_runner(command)
        except FileNotFoundError:
            return _retryable_tool_error("ffmpeg_missing", "ffmpeg is not installed")
        if result.returncode != 0:
            return _retryable_tool_error(
                "ffmpeg_burn_subtitles_failed",
                "ffmpeg subtitle burn-in failed",
                {"stderr": result.stderr},
            )
        return {"path": str(resolved_output)}

    def mux_video_audio(
        self,
        video_path: str | Path,
        audio_path: str | Path,
        output_path: str | Path,
        *,
        duration_sec: float | None = None,
    ) -> dict[str, Any]:
        resolved_video = Path(video_path).resolve()
        resolved_audio = Path(audio_path).resolve()
        resolved_output = Path(output_path).resolve()
        resolved_output.parent.mkdir(parents=True, exist_ok=True)
        command = [
            "ffmpeg",
            "-y",
            "-i",
            str(resolved_video),
            "-i",
            str(resolved_audio),
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-shortest",
        ]
        if duration_sec is not None:
            command.extend(["-t", str(max(0.1, float(duration_sec)))])
        command.append(str(resolved_output))
        try:
            result = self._command_runner(command)
        except FileNotFoundError:
            return _retryable_tool_error("ffmpeg_missing", "ffmpeg is not installed")
        if result.returncode != 0:
            return _retryable_tool_error(
                "ffmpeg_mux_failed",
                "ffmpeg mux failed",
                {"stderr": result.stderr},
            )
        return {"path": str(resolved_output)}

    def mix_audio_tracks(
        self,
        *,
        output_path: str | Path,
        voiceover_specs: list[tuple[str | Path, float, float, float]] | None = None,
        bgm_specs: list[tuple[str | Path, float, float, float]] | None = None,
        duration_sec: float,
        sample_rate: int = 44100,
    ) -> dict[str, Any]:
        """Mix voiceover and BGM clips (path, start_sec, end_sec, volume)."""
        resolved_output = Path(output_path).resolve()
        resolved_output.parent.mkdir(parents=True, exist_ok=True)
        inputs: list[str] = []
        filter_parts: list[str] = []
        index = 0

        for path, start_sec, end_sec, volume in voiceover_specs or []:
            clip_duration = max(0.1, float(end_sec) - float(start_sec))
            inputs.extend(["-i", str(Path(path).resolve())])
            start_ms = max(0, int(float(start_sec) * 1000))
            filter_parts.append(
                f"[{index}:a]atrim=0:{clip_duration},asetpts=PTS-STARTPTS,"
                f"volume={float(volume)},adelay={start_ms}|{start_ms}[a{index}]"
            )
            index += 1

        for path, start_sec, end_sec, volume in bgm_specs or []:
            clip_duration = max(0.1, float(end_sec) - float(start_sec))
            inputs.extend(["-i", str(Path(path).resolve())])
            start_ms = max(0, int(float(start_sec) * 1000))
            filter_parts.append(
                f"[{index}:a]atrim=0:{clip_duration},asetpts=PTS-STARTPTS,"
                f"volume={float(volume)},adelay={start_ms}|{start_ms}[a{index}]"
            )
            index += 1

        if index == 0:
            command = [
                "ffmpeg",
                "-y",
                "-f",
                "lavfi",
                "-i",
                f"anullsrc=r={sample_rate}:cl=stereo",
                "-t",
                str(max(0.1, float(duration_sec))),
                "-c:a",
                "aac",
                str(resolved_output),
            ]
        elif index == 1 and not filter_parts:
            command = [
                "ffmpeg",
                "-y",
                *inputs,
                "-t",
                str(max(0.1, float(duration_sec))),
                "-c:a",
                "aac",
                str(resolved_output),
            ]
        else:
            mix_inputs = "".join(f"[a{i}]" for i in range(index))
            filter_parts.append(
                f"{mix_inputs}amix=inputs={index}:duration=longest:dropout_transition=0[outa]"
            )
            command = [
                "ffmpeg",
                "-y",
                *inputs,
                "-filter_complex",
                ";".join(filter_parts),
                "-map",
                "[outa]",
                "-t",
                str(max(0.1, float(duration_sec))),
                "-c:a",
                "aac",
                str(resolved_output),
            ]

        try:
            result = self._command_runner(command)
        except FileNotFoundError:
            return _retryable_tool_error("ffmpeg_missing", "ffmpeg is not installed")
        if result.returncode != 0:
            return _retryable_tool_error(
                "ffmpeg_mix_audio_failed",
                "ffmpeg audio mix failed",
                {"stderr": result.stderr},
            )
        return {"path": str(resolved_output)}


def fixture_ffmpeg_command_runner() -> CommandRunner:
    """Stub FFmpeg/ffprobe for fixture_mode / CI without real media binaries."""

    def runner(command: list[str]) -> subprocess.CompletedProcess[str]:
        if command and command[0] == "ffprobe":
            payload = {
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
            return subprocess.CompletedProcess(command, 0, stdout=json.dumps(payload), stderr="")

        output = Path(command[-1])
        output.parent.mkdir(parents=True, exist_ok=True)
        if str(output).lower().endswith((".m4a", ".aac", ".wav", ".mp3")):
            output.write_bytes(b"ID3fake-audio")
        else:
            output.write_bytes(b"mock-mp4")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    return runner


def build_fixture_ffmpeg_tool() -> FFmpegTool:
    return FFmpegTool(command_runner=fixture_ffmpeg_command_runner())
