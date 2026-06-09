from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from app.pipelines.sample_pipeline import SampleAnalysisPipeline


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
        return {"language": "en", "segments": []}


class _FakeOpenCVTool:
    extract_keyframes_calls = 0

    def detect_shots(
        self,
        video_path: str,
        *,
        duration_sec: float | None = None,
        output_json_path: Path | None = None,
        min_shot_duration_sec: float | None = None,
    ):
        shots = [
            {"startSec": 0.0, "endSec": 2.0, "confidence": 0.8, "changeReason": "histogram_cut"},
        ]
        if output_json_path is not None:
            output_json_path.parent.mkdir(parents=True, exist_ok=True)
            output_json_path.write_text(json.dumps(shots), encoding="utf-8")
        return {"shots": shots}

    def extract_keyframes(self, video_path: str, shots: list[dict], output_dir: Path, *, keyframes_json_path: Path | None = None):
        type(self).extract_keyframes_calls += 1
        output_dir.mkdir(parents=True, exist_ok=True)
        if keyframes_json_path is not None:
            keyframes_json_path.write_text("[]", encoding="utf-8")
        return {"keyframes": []}


class _FakeYtDlpTool:
    def download(self, *args, **kwargs):
        raise AssertionError("not used")


def _setup_local_video(tmp_path: Path, project_id: str, sample_id: str) -> Path:
    sample_root = tmp_path / "projects" / project_id / "samples" / sample_id
    sample_root.mkdir(parents=True)
    video_path = sample_root / "source.mp4"
    video_path.write_bytes(b"video")
    return video_path


def test_sample_pipeline_writes_poster_when_keyframes_skipped(tmp_path: Path) -> None:
    _FakeOpenCVTool.extract_keyframes_calls = 0
    project_id = "project-1"
    sample_id = "sample-direct"
    video_path = _setup_local_video(tmp_path, project_id, sample_id)
    poster_path = video_path.parent / "poster.jpg"

    def fake_extract(video: Path, output: Path, **kwargs):
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"poster")
        return {"ok": True, "sourceTimeSec": 0.1}

    pipeline = SampleAnalysisPipeline(
        storage_root=tmp_path,
        ffmpeg_tool=_FakeFFmpegTool(),
        whisper_tool=_FakeWhisperTool(),
        opencv_tool=_FakeOpenCVTool(),
        ytdlp_tool=_FakeYtDlpTool(),
    )

    with patch("app.pipelines.sample_pipeline.extract_video_poster", side_effect=fake_extract) as extract_mock:
        summary = pipeline.run(
            project_id=project_id,
            sample_id=sample_id,
            task_id="task-direct",
            video_path=video_path,
            skip_keyframe_extraction=True,
        )

    assert summary["finalEvent"]["status"] == "succeeded"
    assert _FakeOpenCVTool.extract_keyframes_calls == 0
    extract_mock.assert_called()
    assert poster_path.is_file()

    analysis_root = tmp_path / "projects" / project_id / "samples" / sample_id / "analysis"
    assert json.loads((analysis_root / "keyframes.json").read_text(encoding="utf-8")) == []
