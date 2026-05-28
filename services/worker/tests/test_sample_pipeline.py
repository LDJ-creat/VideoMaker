from __future__ import annotations

from pathlib import Path

from app.pipelines.sample_pipeline import SampleAnalysisPipeline


class _FakeYtDlpTool:
    def __init__(self, downloaded_path: Path) -> None:
        self._downloaded_path = downloaded_path

    def download(self, url: str, output_dir: Path, max_duration_sec: int = 180, max_file_size_mb: int = 500):
        self._downloaded_path.parent.mkdir(parents=True, exist_ok=True)
        self._downloaded_path.write_bytes(b"video")
        return {
            "path": str(self._downloaded_path),
            "durationSec": 4.0,
            "ext": "mp4",
            "sourceUrl": url,
        }


class _FakeFFmpegTool:
    def probe(self, video_path: str):
        return {
            "durationSec": 4.0,
            "width": 1280,
            "height": 720,
            "fps": 30.0,
            "videoCodec": "h264",
            "audioCodec": "aac",
            "hasAudio": True,
            "sourcePath": video_path,
        }

    def extract_audio(self, video_path: str, output_path: Path):
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


def test_sample_pipeline_emits_expected_stages_and_writes_artifacts(tmp_path: Path) -> None:
    pipeline = SampleAnalysisPipeline(
        storage_root=tmp_path,
        ffmpeg_tool=_FakeFFmpegTool(),
        whisper_tool=_FakeWhisperTool(),
        opencv_tool=_FakeOpenCVTool(),
        ytdlp_tool=_FakeYtDlpTool(tmp_path / "downloads" / "original.mp4"),
    )

    summary = pipeline.run(
        project_id="project-1",
        task_id="task-1",
        source_url="https://example.com/video",
    )

    assert summary["stages"] == [
        "extracting_metadata",
        "extracting_audio",
        "transcribing",
        "detecting_shots",
        "extracting_keyframes",
        "completed",
    ]

    project_root = tmp_path / "projects" / "project-1"
    assert (project_root / "samples" / "task-1" / "metadata.json").exists()
    assert (project_root / "samples" / "task-1" / "transcript.json").exists()
    assert (project_root / "samples" / "task-1" / "shots.json").exists()
    assert (project_root / "samples" / "task-1" / "keyframes.json").exists()
    assert (project_root / "samples" / "task-1" / "sample-analysis.json").exists()
    assert summary["finalEvent"]["stage"] == "completed"
