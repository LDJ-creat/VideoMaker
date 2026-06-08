from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from app.render.timeline_compiler.compile import compile_timeline_to_mp4
from app.tools.ffmpeg_tool import FFmpegTool


@pytest.mark.integration
def test_compile_timeline_produces_playable_mp4(tmp_path: Path) -> None:
    if os.getenv("RUN_INTEGRATION") != "1":
        pytest.skip("Set RUN_INTEGRATION=1 to run FFmpeg integration tests")
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        pytest.skip("ffmpeg/ffprobe not available on PATH")

    render_root = tmp_path / "render"
    materials = render_root / "materials"
    materials.mkdir(parents=True)

    hook = materials / "hook.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=1080x1920:d=2",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(hook),
        ],
        check=True,
        capture_output=True,
    )
    master = materials / "master.wav"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "sine=f=440:d=2",
            "-c:a",
            "pcm_s16le",
            str(master),
        ],
        check=True,
        capture_output=True,
    )

    timeline = {
        "durationSec": 2,
        "tracks": [
            {
                "id": "video",
                "type": "video",
                "clips": [
                    {
                        "id": "clip-hook",
                        "startSec": 0,
                        "endSec": 2,
                        "sourceRef": "materials/hook.mp4",
                    }
                ],
            },
            {
                "id": "text",
                "type": "text",
                "clips": [
                    {
                        "id": "subtitle-master-1",
                        "startSec": 0,
                        "endSec": 2,
                        "content": "integration",
                        "styleRef": "style://subtitle/clean",
                    }
                ],
            },
            {
                "id": "vo",
                "type": "voiceover",
                "clips": [
                    {
                        "id": "vo-master",
                        "startSec": 0,
                        "endSec": 2,
                        "sourceRef": "materials/master.wav",
                    }
                ],
            },
        ],
    }

    output_path = render_root / "output.mp4"
    result = compile_timeline_to_mp4(
        timeline,
        render_root=render_root,
        output_path=output_path,
        ffmpeg=FFmpegTool(),
        tts_mode="global",
    )
    assert result.ok, result.error
    assert output_path.is_file() and output_path.stat().st_size > 0

    probe = FFmpegTool().probe(output_path)
    assert not probe.get("code")
    assert float(probe.get("durationSec") or 0) >= 1.5
    assert probe.get("hasAudio") is True
    assert result.log.get("status") == "succeeded"
