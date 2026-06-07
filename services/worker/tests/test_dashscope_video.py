from __future__ import annotations

import json
from unittest.mock import MagicMock

import httpx

from app.gateway.providers.base import ProviderConfig
from app.gateway.providers.dashscope_video import (
    DashScopeWanVideoProvider,
    map_wan_duration,
)


def test_map_wan_duration_rounds_up() -> None:
    assert map_wan_duration(5.1) == 10
    assert map_wan_duration(20) == 15
    assert map_wan_duration(3) == 5


def test_dashscope_submit_and_poll_downloads_video(monkeypatch) -> None:
    config = ProviderConfig(
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key="test-key",
        model="",
    )
    client = MagicMock(spec=httpx.Client)

    submit_response = MagicMock()
    submit_response.status_code = 200
    submit_response.json.return_value = {"output": {"task_id": "task-abc"}}
    client.post.return_value = submit_response

    pending = MagicMock()
    pending.status_code = 200
    pending.json.return_value = {"output": {"task_status": "RUNNING"}}

    done = MagicMock()
    done.status_code = 200
    done.json.return_value = {
        "output": {
            "task_status": "SUCCEEDED",
            "video_url": "https://cdn.example/clip.mp4",
        }
    }

    download = MagicMock()
    download.status_code = 200
    download.content = b"mp4-bytes"

    client.get.side_effect = [pending, done, download]

    provider = DashScopeWanVideoProvider(
        config,
        client=client,
        poll_interval_sec=0.01,
        max_poll_sec=30,
    )
    job_id = provider.submit(
        "product hero shot",
        {
            "mode": "t2v",
            "durationSec": 6,
            "resolution": "720P",
        },
    )
    assert job_id == "task-abc"

    result = provider.poll(job_id)
    assert result.video_bytes == b"mp4-bytes"

    post_body = client.post.call_args.kwargs["json"]
    assert post_body["parameters"]["duration"] == 10
    assert "img_url" not in post_body["input"]
    assert post_body["model"] == "wan2.7-t2v"
    assert post_body["parameters"]["resolution"] == "720P"


def test_dashscope_i2v_submit_includes_base64_image(monkeypatch, tmp_path) -> None:
    image_path = tmp_path / "ref.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\n")

    config = ProviderConfig(
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key="test-key",
        model="",
    )
    client = MagicMock(spec=httpx.Client)
    submit_response = MagicMock()
    submit_response.status_code = 200
    submit_response.json.return_value = {"output": {"task_id": "task-i2v"}}
    client.post.return_value = submit_response

    provider = DashScopeWanVideoProvider(config, client=client, poll_interval_sec=0.01, max_poll_sec=5)
    job_id = provider.submit(
        "animate product",
        {
            "mode": "i2v",
            "referenceImagePath": str(image_path),
            "durationSec": 5,
        },
    )
    assert job_id == "task-i2v"
    post_body = client.post.call_args.kwargs["json"]
    assert post_body["model"] == "wan2.6-i2v-flash"
    assert post_body["input"]["img_url"].startswith("data:image/png;base64,")


def test_resolve_video_driver_prefers_dashscope_over_generic_job() -> None:
    from app.gateway.providers.dashscope_video import resolve_video_driver

    assert (
        resolve_video_driver(
            "generic_job",
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
        == "dashscope_wan"
    )
