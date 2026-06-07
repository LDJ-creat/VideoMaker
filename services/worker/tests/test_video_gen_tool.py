import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.runtime.video_gen_quota import VideoGenQuota
from app.tools.image_gen_tool import ToolError
from app.tools.video_gen_tool import VideoGenTool


def test_generate_consumes_quota_only_after_success(tmp_path: Path) -> None:
    video_bytes = b"fake-mp4"
    gateway = MagicMock()
    gateway.submit_video_job.return_value = "job-1"
    poll_result = MagicMock()
    poll_result.video_bytes = video_bytes
    gateway.poll_video_job.return_value = poll_result

    quota = VideoGenQuota(max_slots=1, max_per_slot=1)
    tool = VideoGenTool(gateway=gateway)
    output_path = tmp_path / "clip.mp4"

    ref = tool.generate(
        prompt="ad clip",
        output_path=output_path,
        quota=quota,
        options={"slotId": "slot-a"},
    )

    assert output_path.read_bytes() == video_bytes
    assert quota.used == 1
    assert ref["type"] == "video"


def test_generate_failure_does_not_consume_quota(tmp_path: Path) -> None:
    gateway = MagicMock()
    gateway.submit_video_job.side_effect = RuntimeError("upstream down")
    quota = VideoGenQuota(max_slots=1, max_per_slot=1)
    tool = VideoGenTool(gateway=gateway)

    with pytest.raises(ToolError) as exc_info:
        tool.generate(
            prompt="x",
            output_path=tmp_path / "out.mp4",
            quota=quota,
            options={"slotId": "slot-a"},
        )

    assert exc_info.value.code == "video_generation_failed"
    assert quota.used == 0


def test_generate_rejects_when_quota_exhausted(tmp_path: Path) -> None:
    gateway = MagicMock()
    quota = VideoGenQuota(max_slots=1, max_per_slot=1, consumed_slots={"slot-a": 1})
    tool = VideoGenTool(gateway=gateway)

    with pytest.raises(ToolError) as exc_info:
        tool.generate(
            prompt="x",
            output_path=tmp_path / "out.mp4",
            quota=quota,
            options={"slotId": "slot-a"},
        )

    assert exc_info.value.code == "video_quota_exceeded"
    gateway.submit_video_job.assert_not_called()


def test_generate_resumes_pending_job_without_resubmit(tmp_path: Path) -> None:
    video_bytes = b"fake-mp4"
    gateway = MagicMock()
    poll_result = MagicMock()
    poll_result.video_bytes = video_bytes
    gateway.poll_video_job.return_value = poll_result

    quota = VideoGenQuota(max_slots=1, max_per_slot=1)
    tool = VideoGenTool(gateway=gateway)
    output_path = tmp_path / "slot-a.mp4"
    pending_path = tmp_path / "slot-a.video-job.json"
    pending_path.write_text(
        json.dumps({"jobId": "36e29363-a543-4fe1-b59c-4af769d42b77"}),
        encoding="utf-8",
    )

    ref = tool.generate(
        prompt="ad clip",
        output_path=output_path,
        quota=quota,
        options={"slotId": "slot-a"},
    )

    gateway.submit_video_job.assert_not_called()
    gateway.poll_video_job.assert_called_once_with("36e29363-a543-4fe1-b59c-4af769d42b77")
    assert output_path.read_bytes() == video_bytes
    assert not pending_path.exists()
    assert ref["type"] == "video"


def test_generate_keeps_pending_job_on_poll_timeout(tmp_path: Path) -> None:
    gateway = MagicMock()
    gateway.submit_video_job.return_value = "job-timeout"
    gateway.poll_video_job.side_effect = RuntimeError("did not complete within 300s")

    quota = VideoGenQuota(max_slots=1, max_per_slot=1)
    tool = VideoGenTool(gateway=gateway)
    output_path = tmp_path / "slot-a.mp4"
    pending_path = tmp_path / "slot-a.video-job.json"

    with pytest.raises(ToolError):
        tool.generate(
            prompt="x",
            output_path=output_path,
            quota=quota,
            options={"slotId": "slot-a"},
        )

    assert pending_path.read_text(encoding="utf-8") == json.dumps({"jobId": "job-timeout"})
    assert quota.used == 0
