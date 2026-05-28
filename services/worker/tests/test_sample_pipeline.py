from __future__ import annotations

import json
from pathlib import Path

from app.pipelines.sample_pipeline import SampleAnalysisPipeline


class _FakeYtDlpTool:
    def __init__(self, downloaded_path: Path) -> None:
        self._downloaded_path = downloaded_path

    def download(
        self,
        url: str,
        output_dir: Path,
        *,
        cookies_path: str | Path | None = None,
        max_duration_sec: int = 180,
        max_file_size_mb: int = 500,
    ):
        self._downloaded_path.parent.mkdir(parents=True, exist_ok=True)
        self._downloaded_path.write_bytes(b"video")
        return {
            "path": str(self._downloaded_path),
            "durationSec": 4.0,
            "ext": "mp4",
            "sourceUrl": url,
        }


class _FakeFFmpegTool:
    def __init__(self, has_audio: bool = True) -> None:
        self.has_audio = has_audio
        self.extract_audio_calls = 0
        self.probe_calls = 0

    def probe(self, video_path: str):
        self.probe_calls += 1
        return {
            "durationSec": 4.0,
            "width": 1280,
            "height": 720,
            "fps": 30.0,
            "videoCodec": "h264",
            "audioCodec": "aac" if self.has_audio else None,
            "hasAudio": self.has_audio,
            "sourcePath": video_path,
        }

    def extract_audio(self, video_path: str, output_path: Path):
        self.extract_audio_calls += 1
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"wav")
        return {"path": str(output_path)}


class _FakeWhisperTool:
    def transcribe(self, audio_path: str):
        return {
            "language": "en",
            "segments": [
                {"startSec": 0.0, "endSec": 1.0, "text": "hello", "confidence": 0.95},
            ],
        }


class _FakeOpenCVTool:
    def detect_shots(self, video_path: str, *, duration_sec: float | None = None, output_json_path: Path | None = None):
        shots = [
            {"startSec": 0.0, "endSec": 2.0, "confidence": 0.8, "changeReason": "histogram_cut"},
            {"startSec": 2.0, "endSec": 4.0, "confidence": 0.85, "changeReason": "histogram_cut"},
        ]
        if output_json_path is not None:
            output_json_path.write_text("[]", encoding="utf-8")
        return {"shots": shots}

    def extract_keyframes(self, video_path: str, shots: list[dict], output_dir: Path, *, keyframes_json_path: Path | None = None):
        output_dir.mkdir(parents=True, exist_ok=True)
        keyframes = []
        for idx, shot in enumerate(shots):
            frame = output_dir / f"shot-{idx}-1000.jpg"
            frame.write_bytes(b"jpg")
            keyframes.append(
                {
                    "shotId": f"shot-{idx}",
                    "timeSec": shot["startSec"] + 1.0,
                    "path": str(frame),
                    "score": 0.9,
                    "width": 1280,
                    "height": 720,
                }
            )
        if keyframes_json_path is not None:
            keyframes_json_path.write_text("[]", encoding="utf-8")
        return {"keyframes": keyframes}


def _setup_local_video(tmp_path: Path, project_id: str, sample_id: str) -> Path:
    sample_root = tmp_path / "projects" / project_id / "samples" / sample_id
    sample_root.mkdir(parents=True, exist_ok=True)
    video_path = sample_root / "source.mp4"
    video_path.write_bytes(b"video")
    return video_path


def test_sample_pipeline_emits_expected_stages_and_writes_artifacts(tmp_path: Path) -> None:
    project_id = "project-1"
    sample_id = "sample-1"
    video_path = _setup_local_video(tmp_path, project_id, sample_id)

    pipeline = SampleAnalysisPipeline(
        storage_root=tmp_path,
        ffmpeg_tool=_FakeFFmpegTool(),
        whisper_tool=_FakeWhisperTool(),
        opencv_tool=_FakeOpenCVTool(),
        ytdlp_tool=_FakeYtDlpTool(tmp_path / "downloads" / "original.mp4"),
    )

    summary = pipeline.run(
        project_id=project_id,
        sample_id=sample_id,
        task_id="task-1",
        video_path=video_path,
    )

    assert "extracting_metadata" in summary["stages"]
    assert "transcribing" in summary["stages"]

    analysis_root = tmp_path / "projects" / project_id / "samples" / sample_id / "analysis"
    assert (analysis_root / "metadata.json").exists()
    assert (analysis_root / "transcript.json").exists()
    assert (analysis_root / "shots.json").exists()
    assert (analysis_root / "keyframes.json").exists()
    assert (analysis_root / "sample-analysis.json").exists()
    assert (analysis_root / "checkpoint.json").exists()
    assert summary["finalEvent"]["stage"] == "completed"

    sample_analysis = (analysis_root / "sample-analysis.json").read_text(encoding="utf-8")
    assert '"metadata":' in sample_analysis
    assert '"transcript":' in sample_analysis


def test_sample_pipeline_continues_when_whisper_model_unavailable(tmp_path: Path) -> None:
    class _UnavailableWhisper:
        def transcribe(self, _audio_path: str):
            return {
                "code": "fast_whisper_model_unavailable",
                "message": "Whisper model download or load failed",
                "retryable": True,
            }

    project_id = "project-1"
    sample_id = "sample-1"
    video_path = _setup_local_video(tmp_path, project_id, sample_id)

    pipeline = SampleAnalysisPipeline(
        storage_root=tmp_path,
        ffmpeg_tool=_FakeFFmpegTool(),
        whisper_tool=_UnavailableWhisper(),
        opencv_tool=_FakeOpenCVTool(),
        ytdlp_tool=_FakeYtDlpTool(tmp_path / "downloads" / "original.mp4"),
    )
    summary = pipeline.run(
        project_id=project_id,
        sample_id=sample_id,
        task_id="task-no-whisper-model",
        video_path=video_path,
    )
    assert summary["finalEvent"]["status"] == "succeeded"


def test_sample_pipeline_continues_when_whisper_missing(tmp_path: Path) -> None:
    class _MissingWhisper:
        def transcribe(self, _audio_path: str):
            return {
                "code": "fast_whisper_missing",
                "message": "fast-whisper is not installed",
                "retryable": True,
            }

    project_id = "project-1"
    sample_id = "sample-1"
    video_path = _setup_local_video(tmp_path, project_id, sample_id)

    pipeline = SampleAnalysisPipeline(
        storage_root=tmp_path,
        ffmpeg_tool=_FakeFFmpegTool(),
        whisper_tool=_MissingWhisper(),
        opencv_tool=_FakeOpenCVTool(),
        ytdlp_tool=_FakeYtDlpTool(tmp_path / "downloads" / "original.mp4"),
    )
    summary = pipeline.run(
        project_id=project_id,
        sample_id=sample_id,
        task_id="task-no-whisper",
        video_path=video_path,
    )
    analysis_root = tmp_path / "projects" / project_id / "samples" / sample_id / "analysis"
    transcript = json.loads((analysis_root / "transcript.json").read_text(encoding="utf-8"))
    assert transcript["segments"] == []
    assert summary["finalEvent"]["status"] == "succeeded"


def test_sample_pipeline_skips_audio_and_transcript_when_video_has_no_audio(tmp_path: Path) -> None:
    project_id = "project-1"
    sample_id = "sample-1"
    video_path = _setup_local_video(tmp_path, project_id, sample_id)
    fake_ffmpeg = _FakeFFmpegTool(has_audio=False)
    pipeline = SampleAnalysisPipeline(
        storage_root=tmp_path,
        ffmpeg_tool=fake_ffmpeg,
        whisper_tool=_FakeWhisperTool(),
        opencv_tool=_FakeOpenCVTool(),
        ytdlp_tool=_FakeYtDlpTool(tmp_path / "downloads" / "original.mp4"),
    )

    summary = pipeline.run(
        project_id=project_id,
        sample_id=sample_id,
        task_id="task-no-audio",
        video_path=video_path,
    )

    analysis_root = tmp_path / "projects" / project_id / "samples" / sample_id / "analysis"
    assert fake_ffmpeg.extract_audio_calls == 0
    assert not (analysis_root / "audio.wav").exists()
    assert (analysis_root / "transcript.json").exists()
    assert summary["finalEvent"]["status"] == "succeeded"


def test_sample_pipeline_resume_skips_completed_stages_after_transcribing_failure(tmp_path: Path) -> None:
    project_id = "project-1"
    sample_id = "sample-1"
    video_path = _setup_local_video(tmp_path, project_id, sample_id)

    class _FailOnceWhisper:
        def __init__(self) -> None:
            self.calls = 0

        def transcribe(self, _audio_path: str):
            self.calls += 1
            if self.calls == 1:
                return {
                    "code": "fast_whisper_timeout",
                    "message": "transient failure",
                    "retryable": True,
                }
            return {
                "language": "en",
                "segments": [{"startSec": 0.0, "endSec": 1.0, "text": "hello", "confidence": 0.9}],
            }

    fake_ffmpeg = _FakeFFmpegTool()
    whisper = _FailOnceWhisper()
    pipeline = SampleAnalysisPipeline(
        storage_root=tmp_path,
        ffmpeg_tool=fake_ffmpeg,
        whisper_tool=whisper,
        opencv_tool=_FakeOpenCVTool(),
        ytdlp_tool=_FakeYtDlpTool(tmp_path / "downloads" / "original.mp4"),
    )

    failed = pipeline.run(
        project_id=project_id,
        sample_id=sample_id,
        task_id="task-resume",
        video_path=video_path,
    )
    assert failed["finalEvent"]["status"] == "failed"
    assert fake_ffmpeg.probe_calls == 1
    assert fake_ffmpeg.extract_audio_calls == 1

    fake_ffmpeg.probe_calls = 0
    fake_ffmpeg.extract_audio_calls = 0

    resumed = pipeline.run(
        project_id=project_id,
        sample_id=sample_id,
        task_id="task-resume",
        video_path=video_path,
        resume=True,
    )
    assert resumed["finalEvent"]["status"] == "succeeded"
    assert fake_ffmpeg.probe_calls == 0
    assert fake_ffmpeg.extract_audio_calls == 0
    assert "extracting_metadata" in resumed["resumeSummary"]["skippedStages"]
    assert "extracting_audio" in resumed["resumeSummary"]["skippedStages"]
