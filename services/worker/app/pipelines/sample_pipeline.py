from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.runtime.checkpoint import AnalysisCheckpoint, should_skip_analysis_stage
from app.runtime.task_context import TaskContext
from app.tools.ffmpeg_tool import FFmpegTool
from app.tools.opencv_tool import OpenCVTool
from app.tools.whisper_tool import WHISPER_SOFT_FAIL_CODES, WhisperTool
from app.tools.ytdlp_tool import YtDlpTool


def _is_tool_error(payload: dict[str, Any]) -> bool:
    return "code" in payload and "retryable" in payload


def _append_tool_warning(warnings: list[str], payload: dict[str, Any]) -> None:
    warning = payload.get("warning")
    if not isinstance(warning, dict):
        return
    code = str(warning.get("code") or "tool_warning")
    message = str(warning.get("message") or "")
    text = f"{code}: {message}" if message else code
    if text not in warnings:
        warnings.append(text)


def _read_json(path: Path) -> Any | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


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

    def _resolve_sample_video(
        self,
        sample_root: Path,
        *,
        video_path: str | Path | None,
        checkpoint: AnalysisCheckpoint,
    ) -> Path | None:
        if video_path is not None:
            candidate = Path(video_path).resolve()
            if candidate.is_file():
                return candidate
        if checkpoint.videoPath:
            candidate = Path(checkpoint.videoPath).resolve()
            if candidate.is_file():
                return candidate
        for name in ("source.mp4", "original.mp4"):
            candidate = sample_root / name
            if candidate.is_file() and candidate.stat().st_size > 0:
                return candidate.resolve()
        return None

    def run(
        self,
        project_id: str,
        sample_id: str,
        task_id: str,
        video_path: str | Path | None = None,
        source_url: str | None = None,
        cookies_path: str | Path | None = None,
        *,
        resume: bool = False,
    ) -> dict[str, Any]:
        context = TaskContext(project_id=project_id, task_id=task_id, storage_root=self._storage_root)
        sample_root = context.artifacts.resolve(Path("samples") / sample_id)
        analysis_rel_dir = Path("samples") / sample_id / "analysis"
        analysis_root = context.artifacts.resolve(analysis_rel_dir)
        analysis_root.mkdir(parents=True, exist_ok=True)

        checkpoint_path = analysis_root / "checkpoint.json"
        checkpoint = AnalysisCheckpoint.load(checkpoint_path)
        if not checkpoint.sampleId:
            checkpoint.sampleId = sample_id

        skipped_stages: list[str] = []
        executed_stages: list[str] = []
        pipeline_warnings: list[str] = []

        selected_video_path = self._resolve_sample_video(
            sample_root,
            video_path=video_path,
            checkpoint=checkpoint,
        )

        if source_url is not None:
            if should_skip_analysis_stage("downloading", checkpoint, analysis_root, resume=resume):
                skipped_stages.append("downloading")
                if selected_video_path is None:
                    selected_video_path = self._resolve_sample_video(
                        sample_root,
                        video_path=None,
                        checkpoint=checkpoint,
                    )
                context.emit_event(
                    "extracting_metadata",
                    10,
                    "(resumed) sample video already downloaded",
                )
            else:
                executed_stages.append("downloading")
                download_dir = sample_root
                download_dir.mkdir(parents=True, exist_ok=True)
                download_result = self._ytdlp_tool.download(
                    source_url,
                    download_dir,
                    cookies_path=cookies_path,
                )
                if _is_tool_error(download_result):
                    checkpoint.mark_failed("downloading")
                    checkpoint.save(checkpoint_path)
                    failed_event = context.emit_event(
                        "extracting_metadata",
                        0,
                        "sample download failed",
                        status="failed",
                        error=download_result,
                    )
                    return self._result(context, failed_event, skipped_stages, executed_stages)
                selected_video_path = Path(download_result["path"]).resolve()
                checkpoint.videoPath = str(selected_video_path)
                checkpoint.mark_stage_complete("downloading")
                checkpoint.save(checkpoint_path)
                context.register_artifact("video", selected_video_path)

        if selected_video_path is None and video_path is not None:
            selected_video_path = Path(video_path).resolve()

        if selected_video_path is None:
            checkpoint.mark_failed("extracting_metadata")
            checkpoint.save(checkpoint_path)
            failed_event = context.emit_event(
                "extracting_metadata",
                0,
                "missing sample video input",
                status="failed",
                error={"code": "sample_input_missing", "retryable": False},
            )
            return self._result(context, failed_event, skipped_stages, executed_stages)

        checkpoint.videoPath = str(selected_video_path)

        metadata: dict[str, Any]
        metadata_path = analysis_root / "metadata.json"
        if should_skip_analysis_stage("extracting_metadata", checkpoint, analysis_root, resume=resume):
            skipped_stages.append("extracting_metadata")
            metadata = _read_json(metadata_path) or {}
            context.emit_event("extracting_metadata", 15, "(resumed) metadata already extracted")
        else:
            executed_stages.append("extracting_metadata")
            context.emit_event("extracting_metadata", 15, "extracting video metadata")
            metadata = self._ffmpeg_tool.probe(str(selected_video_path))
            if _is_tool_error(metadata):
                checkpoint.mark_failed("extracting_metadata")
                checkpoint.save(checkpoint_path)
                failed_event = context.emit_event(
                    "extracting_metadata",
                    15,
                    "metadata extraction failed",
                    status="failed",
                    error=metadata,
                )
                return self._result(context, failed_event, skipped_stages, executed_stages)
            metadata_path = context.artifacts.write_json(analysis_rel_dir / "metadata.json", metadata)
            context.register_artifact("json", metadata_path)
            checkpoint.mark_stage_complete("extracting_metadata")
            checkpoint.save(checkpoint_path)

        audio_path: Path | None = None
        transcript: dict[str, Any] = {"language": "unknown", "segments": []}

        if should_skip_analysis_stage(
            "extracting_audio",
            checkpoint,
            analysis_root,
            resume=resume,
            metadata=metadata,
        ):
            skipped_stages.append("extracting_audio")
            if metadata.get("hasAudio"):
                candidate = analysis_root / "audio.wav"
                if candidate.is_file():
                    audio_path = candidate
            context.emit_event("extracting_audio", 30, "(resumed) audio already extracted")
        elif metadata.get("hasAudio"):
            executed_stages.append("extracting_audio")
            context.emit_event("extracting_audio", 30, "extracting sample audio")
            audio_path = context.artifacts.resolve(analysis_rel_dir / "audio.wav")
            audio = self._ffmpeg_tool.extract_audio(str(selected_video_path), audio_path)
            if _is_tool_error(audio):
                checkpoint.mark_failed("extracting_audio")
                checkpoint.save(checkpoint_path)
                failed_event = context.emit_event(
                    "extracting_audio",
                    30,
                    "audio extraction failed",
                    status="failed",
                    error=audio,
                )
                return self._result(context, failed_event, skipped_stages, executed_stages)
            context.register_artifact("audio", audio_path)
            checkpoint.mark_stage_complete("extracting_audio")
            checkpoint.save(checkpoint_path)
        else:
            executed_stages.append("extracting_audio")
            context.emit_event("extracting_audio", 30, "audio track missing, skip extraction")
            checkpoint.mark_stage_complete("extracting_audio")
            checkpoint.save(checkpoint_path)

        if should_skip_analysis_stage("transcribing", checkpoint, analysis_root, resume=resume):
            skipped_stages.append("transcribing")
            transcript = _read_json(analysis_root / "transcript.json") or transcript
            context.emit_event("transcribing", 45, "(resumed) transcript already available")
        elif audio_path is not None:
            executed_stages.append("transcribing")
            context.emit_event("transcribing", 45, "running whisper transcription")
            transcript = self._whisper_tool.transcribe(str(audio_path))
            if _is_tool_error(transcript):
                if transcript.get("code") in WHISPER_SOFT_FAIL_CODES:
                    context.emit_event(
                        "transcribing",
                        45,
                        "whisper unavailable, continuing with empty transcript",
                    )
                    transcript = {
                        "language": "unknown",
                        "segments": [],
                        "warnings": [str(transcript.get("message", "whisper unavailable"))],
                    }
                else:
                    checkpoint.mark_failed("transcribing")
                    checkpoint.save(checkpoint_path)
                    failed_event = context.emit_event(
                        "transcribing",
                        45,
                        "transcription failed",
                        status="failed",
                        error=transcript,
                    )
                    return self._result(context, failed_event, skipped_stages, executed_stages)
            transcript_path = context.artifacts.write_json(analysis_rel_dir / "transcript.json", transcript)
            context.register_artifact("json", transcript_path)
            checkpoint.mark_stage_complete("transcribing")
            checkpoint.save(checkpoint_path)
        else:
            executed_stages.append("transcribing")
            context.emit_event("transcribing", 45, "audio missing, use empty transcript")
            transcript_path = context.artifacts.write_json(analysis_rel_dir / "transcript.json", transcript)
            context.register_artifact("json", transcript_path)
            checkpoint.mark_stage_complete("transcribing")
            checkpoint.save(checkpoint_path)

        shots: list[dict[str, Any]]
        if should_skip_analysis_stage("detecting_shots", checkpoint, analysis_root, resume=resume):
            skipped_stages.append("detecting_shots")
            shots = _read_json(analysis_root / "shots.json") or []
            context.emit_event("detecting_shots", 60, "(resumed) shots already detected")
        else:
            executed_stages.append("detecting_shots")
            context.emit_event("detecting_shots", 60, "detecting video shots")
            shots_result = self._opencv_tool.detect_shots(
                str(selected_video_path),
                duration_sec=float(metadata.get("durationSec", 0.0)),
            )
            _append_tool_warning(pipeline_warnings, shots_result)
            shots = shots_result.get("shots", [])
            shots_path = context.artifacts.write_json(analysis_rel_dir / "shots.json", shots)
            context.register_artifact("json", shots_path)
            checkpoint.mark_stage_complete("detecting_shots")
            checkpoint.save(checkpoint_path)

        keyframes: list[dict[str, Any]]
        if should_skip_analysis_stage("extracting_keyframes", checkpoint, analysis_root, resume=resume):
            skipped_stages.append("extracting_keyframes")
            keyframes = _read_json(analysis_root / "keyframes.json") or []
            context.emit_event("extracting_keyframes", 80, "(resumed) keyframes already extracted")
        else:
            executed_stages.append("extracting_keyframes")
            context.emit_event("extracting_keyframes", 80, "extracting representative keyframes")
            keyframes_result = self._opencv_tool.extract_keyframes(
                str(selected_video_path),
                shots,
                context.artifacts.resolve(analysis_rel_dir / "keyframes"),
            )
            _append_tool_warning(pipeline_warnings, keyframes_result)
            keyframes = keyframes_result.get("keyframes", [])
            keyframes_path = context.artifacts.write_json(analysis_rel_dir / "keyframes.json", keyframes)
            context.register_artifact("json", keyframes_path)
            checkpoint.mark_stage_complete("extracting_keyframes")
            checkpoint.save(checkpoint_path)

        if should_skip_analysis_stage("consolidating", checkpoint, analysis_root, resume=resume):
            skipped_stages.append("consolidating")
            context.emit_event("completed", 95, "(resumed) sample analysis artifacts ready")
        else:
            executed_stages.append("consolidating")
            metadata_path = analysis_root / "metadata.json"
            transcript_path = analysis_root / "transcript.json"
            shots_path = analysis_root / "shots.json"
            keyframes_path = analysis_root / "keyframes.json"
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
                "warnings": [
                    *list(transcript.get("warnings") or []),
                    *pipeline_warnings,
                ],
                "sourcePath": str(selected_video_path),
            }
            sample_analysis_path = context.artifacts.write_json(
                analysis_rel_dir / "sample-analysis.json",
                sample_analysis,
            )
            context.register_artifact("json", sample_analysis_path)
            checkpoint.mark_stage_complete("consolidating")
            checkpoint.save(checkpoint_path)

        final_event = context.emit_event(
            "completed",
            100,
            "sample analysis completed",
            status="succeeded",
            artifact_refs=context.artifact_refs,
        )
        return self._result(context, final_event, skipped_stages, executed_stages)

    def _result(
        self,
        context: TaskContext,
        final_event: dict[str, Any],
        skipped_stages: list[str],
        executed_stages: list[str],
    ) -> dict[str, Any]:
        return {
            "stages": [event["stage"] for event in context.emitted_events],
            "artifactRefs": context.artifact_refs,
            "finalEvent": final_event,
            "resumeSummary": {
                "skippedStages": skipped_stages,
                "executedStages": executed_stages,
            },
        }
