from __future__ import annotations

from unittest.mock import MagicMock

import httpx
import pytest

from app.gateway.providers.base import GatewayError, ProviderConfig
from app.gateway.providers.pluggable_video import create_video_provider
from app.gateway.providers.volcengine_seeddance_video import VolcengineSeedDanceVideoProvider
from model_gateway.video_driver import map_seeddance_duration


def test_map_seeddance_duration_clamps_range() -> None:
    assert map_seeddance_duration(3) == 4
    assert map_seeddance_duration(12.2) == 13


def test_seeddance_submit_and_poll_downloads_video() -> None:
    config = ProviderConfig(
        base_url="https://ark.cn-beijing.volces.com/api/v3",
        api_key="test-key",
        model="doubao-seedance-2-0-260128",
    )
    client = MagicMock(spec=httpx.Client)

    submit_response = MagicMock()
    submit_response.status_code = 200
    submit_response.json.return_value = {"id": "cgt-task-abc"}
    client.post.return_value = submit_response

    pending = MagicMock()
    pending.status_code = 200
    pending.json.return_value = {"status": "running"}

    done = MagicMock()
    done.status_code = 200
    done.json.return_value = {
        "status": "succeeded",
        "content": {"video_url": "https://cdn.example/clip.mp4"},
    }

    download = MagicMock()
    download.status_code = 200
    download.content = b"mp4-bytes"

    client.get.side_effect = [pending, done, download]

    provider = VolcengineSeedDanceVideoProvider(
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
            "aspectRatio": "9:16",
        },
    )
    assert job_id == "cgt-task-abc"

    result = provider.poll(job_id)
    assert result.video_bytes == b"mp4-bytes"

    post_body = client.post.call_args.kwargs["json"]
    assert post_body["duration"] == 6
    assert post_body["ratio"] == "9:16"
    assert post_body["resolution"] == "720p"
    assert post_body["model"] == "doubao-seedance-2-0-260128"
    assert post_body["content"] == [{"type": "text", "text": "product hero shot"}]


def test_seeddance_i2v_submit_includes_base64_image(tmp_path) -> None:
    image_path = tmp_path / "ref.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\n")

    config = ProviderConfig(
        base_url="https://ark.cn-beijing.volces.com/api/v3",
        api_key="test-key",
        model="",
    )
    client = MagicMock(spec=httpx.Client)
    submit_response = MagicMock()
    submit_response.status_code = 200
    submit_response.json.return_value = {"id": "cgt-task-i2v"}
    client.post.return_value = submit_response

    provider = VolcengineSeedDanceVideoProvider(
        config,
        client=client,
        poll_interval_sec=0.01,
        max_poll_sec=5,
    )
    job_id = provider.submit(
        "animate product",
        {
            "mode": "i2v",
            "referenceImagePath": str(image_path),
            "durationSec": 5,
            "aspectRatio": "16:9",
        },
    )
    assert job_id == "cgt-task-i2v"
    post_body = client.post.call_args.kwargs["json"]
    assert post_body["ratio"] == "adaptive"
    assert post_body["model"] == "doubao-seedance-2-0-260128"
    image_part = post_body["content"][1]
    assert image_part["type"] == "image_url"
    assert image_part["image_url"]["url"].startswith("data:image/png;base64,")


def test_seeddance_poll_raises_on_failed_status() -> None:
    config = ProviderConfig(
        base_url="https://ark.cn-beijing.volces.com/api/v3",
        api_key="test-key",
        model="doubao-seedance-2-0-260128",
    )
    client = MagicMock(spec=httpx.Client)
    failed = MagicMock()
    failed.status_code = 200
    failed.json.return_value = {"status": "failed", "error": {"message": "policy violation"}}
    client.get.return_value = failed

    provider = VolcengineSeedDanceVideoProvider(
        config,
        client=client,
        poll_interval_sec=0.01,
        max_poll_sec=5,
    )
    with pytest.raises(GatewayError) as exc_info:
        provider.poll("cgt-failed")
    assert exc_info.value.code == "video_job_failed"


def test_create_video_provider_supports_volcengine_seeddance() -> None:
    config = ProviderConfig(
        base_url="https://ark.cn-beijing.volces.com/api/v3",
        api_key="test-key",
        model="doubao-seedance-2-0-260128",
    )
    provider = create_video_provider("volcengine_seeddance", config)
    assert isinstance(provider, VolcengineSeedDanceVideoProvider)
