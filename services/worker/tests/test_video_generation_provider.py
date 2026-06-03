from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from app.providers.material_types import MaterialContext
from app.providers.video_generation_provider import VideoGenerationProvider
from app.runtime.video_gen_quota import VideoGenQuota
from app.tools.video_gen_tool import VideoGenTool


def test_video_provider_passes_i2v_options(tmp_path: Path) -> None:
    image_path = tmp_path / "ref.png"
    image_path.write_bytes(b"png")

    gateway = MagicMock()
    gateway.submit_video_job.return_value = "job-1"
    poll = MagicMock()
    poll.video_bytes = b"mp4"
    gateway.poll_video_job.return_value = poll

    tool = VideoGenTool(gateway=gateway)
    provider = VideoGenerationProvider(tool)

    generated_root = tmp_path / "generated"
    generated_root.mkdir()
    render_root = tmp_path / "renders"
    render_root.mkdir()

    ctx = MaterialContext(
        project_id="p1",
        generation_id="g1",
        render_root=render_root,
        generated_root=generated_root,
        gateway=gateway,
        quota=VideoGenQuota(max_slots=3, max_per_slot=1),
        inventory={
            "assets": [{"id": "asset-1", "type": "image", "uri": str(image_path)}],
            "candidateMoments": [],
        },
        slot_matches=[
            {"slotId": "slot2", "assetId": "asset-1", "matchScore": 0.42},
        ],
        storyboard=[
            {
                "slotId": "slot2",
                "startSec": 5.0,
                "endSec": 25.0,
                "visual": "product on beach",
                "script": "show benefits",
            }
        ],
        structure={
            "slots": [
                {
                    "id": "slot2",
                    "role": "usage_scene",
                    "visualIntent": "lifestyle",
                    "scriptIntent": "benefits",
                }
            ]
        },
        emit_progress=lambda *_args: None,
        register_artifact=lambda t, p: {"type": t, "uri": str(p)},
    )

    action = {"id": "action-slot2", "slotId": "slot2", "provider": "video_generation"}
    result = provider.execute(action, ctx)

    assert result["ok"] is True
    options = gateway.submit_video_job.call_args.kwargs["options"]
    assert options["mode"] == "i2v"
    assert options["slotId"] == "slot2"
    assert options["durationSec"] == 20.0
    assert Path(options["referenceImagePath"]) == image_path


def test_video_provider_downgrades_i2v_when_reference_missing(tmp_path: Path) -> None:
    gateway = MagicMock()
    gateway.submit_video_job.return_value = "job-1"
    poll = MagicMock()
    poll.video_bytes = b"mp4"
    gateway.poll_video_job.return_value = poll

    provider = VideoGenerationProvider(VideoGenTool(gateway=gateway))
    generated_root = tmp_path / "generated"
    generated_root.mkdir()

    ctx = MaterialContext(
        project_id="p1",
        generation_id="g1",
        render_root=tmp_path / "renders",
        generated_root=generated_root,
        gateway=gateway,
        quota=VideoGenQuota(max_slots=3, max_per_slot=1),
        inventory={
            "assets": [{"id": "asset-1", "type": "image", "uri": "/missing/ref.png"}],
            "candidateMoments": [],
        },
        slot_matches=[{"slotId": "slot2", "assetId": "asset-1", "matchScore": 0.42}],
        storyboard=[{"slotId": "slot2", "startSec": 0.0, "endSec": 5.0, "visual": "x", "script": ""}],
        structure={"slots": [{"id": "slot2", "role": "usage_scene"}]},
        emit_progress=lambda *_args: None,
        register_artifact=lambda t, p: {"type": t, "uri": str(p)},
    )

    result = provider.execute(
        {"id": "action-slot2", "slotId": "slot2", "provider": "video_generation"},
        ctx,
    )
    assert result["ok"] is True
    assert gateway.submit_video_job.call_args.kwargs["options"]["mode"] == "t2v"
    assert "referenceImagePath" not in gateway.submit_video_job.call_args.kwargs["options"]
