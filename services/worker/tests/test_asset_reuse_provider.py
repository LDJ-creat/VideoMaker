from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.providers.asset_reuse_provider import AssetReuseProvider
from app.providers.material_types import MaterialContext
from app.tools.ffmpeg_tool import FFmpegTool


def _write_test_png(path: Path) -> None:
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not installed")
    path.parent.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:s=64x64:d=0.1",
            "-frames:v",
            "1",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0 or not path.is_file():
        pytest.skip("ffmpeg could not create test png")


def test_asset_reuse_rejects_image_assets(tmp_path: Path) -> None:
    image_path = tmp_path / "source.png"
    _write_test_png(image_path)
    generated_root = tmp_path / "projects" / "p1" / "generations" / "g1" / "generated"
    render_root = tmp_path / "projects" / "p1" / "renders" / "g1"
    generated_root.mkdir(parents=True)
    render_root.mkdir(parents=True)

    provider = AssetReuseProvider(ffmpeg_tool=FFmpegTool())
    ctx = MaterialContext(
        project_id="p1",
        generation_id="g1",
        render_root=render_root,
        generated_root=generated_root,
        gateway=MagicMock(),
        quota=MagicMock(),
        inventory={
            "assets": [{"id": "asset-1", "type": "image", "uri": str(image_path)}],
            "candidateMoments": [],
        },
        storyboard=[
            {
                "id": "scene-2",
                "slotId": "slot2",
                "startSec": 5.0,
                "endSec": 25.0,
                "visual": "",
                "script": "",
            }
        ],
        slot_matches=[
            {
                "slotId": "slot2",
                "assetId": "asset-1",
                "momentId": None,
                "matchScore": 0.4,
            }
        ],
        structure={"slots": []},
        emit_progress=lambda *_args: None,
        register_artifact=lambda artifact_type, path: {
            "type": artifact_type,
            "uri": str(path),
        },
    )
    action = {"id": "action-slot2", "slotId": "slot2", "provider": "asset_reuse"}

    result = provider.execute(action, ctx)

    assert result["ok"] is False
    assert result.get("error", {}).get("code") == "asset_reuse_image_not_supported"
    assert not (generated_root / "slot2-reuse.mp4").is_file()
