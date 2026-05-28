from __future__ import annotations

from pathlib import Path
from typing import Any

from app.runtime.task_context import TaskContext
from app.tools.ffmpeg_tool import FFmpegTool
from app.tools.opencv_tool import OpenCVTool
from app.tools.whisper_tool import WhisperTool
from app.tools.ytdlp_tool import YtDlpTool


def _is_tool_error(payload: dict[str, Any]) -> bool:
    return "code" in payload and "retryable" in payload


class SampleAnalysisPipeline:
    def __init__(
        self,
        storage_root: str | Path,
        *,
        ffmpeg_tool: FFmpegTool | None = None,
        whisper_tool: WhisperTool | None = None,
        opencv_tool: OpenCVTool | None = None,
        ytdlp_tool: YtDlpTool | None = None,
    ) -> None:
        self._storage_root = Path(storage_root)
        self._ffmpeg_tool = ffmpeg_tool or FFmpegTool()
        self._whisper_tool = whisper_tool or WhisperTool()
        self._opencv_tool = opencv_tool or OpenCVTool()
        self._ytdlp_tool = ytdlp_tool or YtDlpTool()

    def run(
        self,
        project_id: str,
        task_id: str,
        video_path: str | Path | None = None,
        source_url: str | None = None,
    ) -> dict[str, Any]:
        context = TaskContext(project_id=project_id, task_id=task_id, storage_root=self._storage_root)
        sample_rel_dir = Path("samples") / task_id
        sample_root = context.artifacts.resolve(sample_rel_dir)
        sample_root.mkdir(parents=True, exist_ok=True)

        selected_video_path = Path(video_path).resolve() if video_path is not None else None
        if source_url is not None:
            download_result = self._ytdlp_tool.download(source_url, sample_root)
            if _is_tool_error(download_result):
                failed_event = context.emit_event(
                    "extracting_metadata",
                    0,
                    "sample download failed",
                    status="failed",
                    error=download_result,
                )
                return {
                    "stages": [event["stage"] for event in context.emitted_events],
                    "artifactRefs": context.artifact_refs,
                    "finalEvent": failed_event,
                }
            selected_video_path = Path(download_result["path"]).resolve()
            context.register_artifact("video", selected_video_path)

        if selected_video_path is None:
            failed_event = context.emit_event(
                "extracting_metadata",
                0,
                "missing sample video input",
                status="failed",
                error={"code": "sample_input_missing", "retryable": False},
            )
            return {
                "stages": [event["stage"] for event in context.emitted_events],
                "artifactRefs": context.artifact_refs,
                "finalEvent": failed_event,
            }

        metadata_event = context.emit_event("extracting_metadata", 15, "extracting video metadata")
        metadata = self._ffmpeg_tool.probe(str(selected_video_path))
        if _is_tool_error(metadata):
            metadata_event = context.emit_event(
                "extracting_metadata",
                15,
                "metadata extraction failed",
                status="failed",
                error=metadata,
            )
            return {
                "stages": [event["stage"] for event in context.emitted_events],
                "artifactRefs": context.artifact_refs,
                "finalEvent": metadata_event,
            }
        metadata_path = context.artifacts.write_json(sample_rel_dir / "metadata.json", metadata)
        context.register_artifact("json", metadata_path)

        audio_path: Path | None = None
        transcript: dict[str, Any] = {"language": "unknown", "segments": []}

        if metadata.get("hasAudio"):
            context.emit_event("extracting_audio", 30, "extracting sample audio")
            audio_path = context.artifacts.resolve(sample_rel_dir / "audio.wav")
            audio = self._ffmpeg_tool.extract_audio(str(selected_video_path), audio_path)
            if _is_tool_error(audio):
                audio_event = context.emit_event(
                    "extracting_audio",
                    30,
                    "audio extraction failed",
                    status="failed",
                    error=audio,
                )
                return {
                    "stages": [event["stage"] for event in context.emitted_events],
                    "artifactRefs": context.artifact_refs,
                    "finalEvent": audio_event,
                }
            context.register_artifact("audio", audio_path)
        else:
            context.emit_event("extracting_audio", 30, "audio track missing, skip extraction")

        if audio_path is not None:
            context.emit_event("transcribing", 45, "running whisper transcription")
            transcript = self._whisper_tool.transcribe(audio_path)
            if _is_tool_error(transcript):
                transcript_event = context.emit_event(
                    "transcribing",
                    45,
                    "transcription failed",
                    status="failed",
                    error=transcript,
                )
                return {
                    "stages": [event["stage"] for event in context.emitted_events],
                    "artifactRefs": context.artifact_refs,
                    "finalEvent": transcript_event,
                }
        else:
            context.emit_event("transcribing", 45, "audio missing, use empty transcript")
        transcript_path = context.artifacts.write_json(sample_rel_dir / "transcript.json", transcript)
        context.register_artifact("json", transcript_path)

        context.emit_event("detecting_shots", 60, "detecting video shots")
        shots_result = self._opencv_tool.detect_shots(
            str(selected_video_path),
            duration_sec=float(metadata.get("durationSec", 0.0)),
        )
        shots = shots_result.get("shots", [])
        shots_path = context.artifacts.write_json(sample_rel_dir / "shots.json", shots)
        context.register_artifact("json", shots_path)

        context.emit_event("extracting_keyframes", 80, "extracting representative keyframes")
        keyframes_result = self._opencv_tool.extract_keyframes(
            str(selected_video_path),
            shots,
            context.artifacts.resolve(sample_rel_dir / "keyframes"),
        )
        keyframes = keyframes_result.get("keyframes", [])
        keyframes_path = context.artifacts.write_json(sample_rel_dir / "keyframes.json", keyframes)
        context.register_artifact("json", keyframes_path)

        sample_analysis = {
            "metadataPath": str(metadata_path),
            "audioPath": str(audio_path) if audio_path is not None else None,
            "transcriptPath": str(transcript_path),
            "shotsPath": str(shots_path),
            "keyframesPath": str(keyframes_path),
            "metadata": metadata,
            "transcript": transcript,
            "shots": shots,
            "keyframes": keyframes,
            "warnings": [item for item in [shots_result.get("warning"), keyframes_result.get("warning")] if item],
            "sourcePath": str(selected_video_path),
        }
        sample_analysis_path = context.artifacts.write_json(sample_rel_dir / "sample-analysis.json", sample_analysis)
        context.register_artifact("json", sample_analysis_path)

        final_event = context.emit_event(
            "completed",
            100,
            "sample analysis completed",
            status="succeeded",
            artifact_refs=context.artifact_refs,
        )
        return {
            "stages": [event["stage"] for event in context.emitted_events],
            "artifactRefs": context.artifact_refs,
            "finalEvent": final_event,
        }
