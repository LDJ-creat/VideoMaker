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

    quota = VideoGenQuota(max_calls=1)
    tool = VideoGenTool(gateway=gateway)
    output_path = tmp_path / "clip.mp4"

    ref = tool.generate(prompt="ad clip", output_path=output_path, quota=quota)

    assert output_path.read_bytes() == video_bytes
    assert quota.used == 1
    assert ref["type"] == "video"


def test_generate_failure_does_not_consume_quota(tmp_path: Path) -> None:
    gateway = MagicMock()
    gateway.submit_video_job.side_effect = RuntimeError("upstream down")
    quota = VideoGenQuota(max_calls=1)
    tool = VideoGenTool(gateway=gateway)

    with pytest.raises(ToolError) as exc_info:
        tool.generate(prompt="x", output_path=tmp_path / "out.mp4", quota=quota)

    assert exc_info.value.code == "video_generation_failed"
    assert quota.used == 0


def test_generate_rejects_when_quota_exhausted(tmp_path: Path) -> None:
    gateway = MagicMock()
    quota = VideoGenQuota(max_calls=1, used=1)
    tool = VideoGenTool(gateway=gateway)

    with pytest.raises(ToolError) as exc_info:
        tool.generate(prompt="x", output_path=tmp_path / "out.mp4", quota=quota)

    assert exc_info.value.code == "video_quota_exceeded"
    gateway.submit_video_job.assert_not_called()
