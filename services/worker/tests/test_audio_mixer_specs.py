from __future__ import annotations

from pathlib import Path

from app.pipelines.tts_mode import VO_MASTER_CLIP_ID
from app.render.timeline_compiler.audio_mixer import collect_voiceover_specs


def test_collect_voiceover_specs_global_master(tmp_path: Path) -> None:
    render_root = tmp_path / "render"
    materials = render_root / "materials"
    materials.mkdir(parents=True)
    (materials / "master.wav").write_bytes(b"wav")

    timeline = {
        "durationSec": 30,
        "tracks": [
            {
                "id": "vo",
                "type": "voiceover",
                "clips": [
                    {
                        "id": VO_MASTER_CLIP_ID,
                        "startSec": 0,
                        "endSec": 30,
                        "sourceRef": "materials/master.wav",
                    }
                ],
            }
        ],
    }

    specs = collect_voiceover_specs(
        timeline,
        render_root=render_root,
        target_duration_sec=30,
        tts_mode="global",
    )
    assert len(specs) == 1
    assert specs[0][1] == 0.0
    assert specs[0][2] == 30.0


def test_collect_voiceover_specs_from_timeline_clips(tmp_path: Path) -> None:
    """Legacy multi-clip timelines may still expose per-slot voiceover windows."""
    render_root = tmp_path / "render"
    materials = render_root / "materials"
    materials.mkdir(parents=True)
    (materials / "slot-a.wav").write_bytes(b"a")
    (materials / "slot-b.wav").write_bytes(b"b")

    timeline = {
        "durationSec": 10,
        "tracks": [
            {
                "id": "vo",
                "type": "voiceover",
                "clips": [
                    {
                        "id": "vo-slot-a",
                        "startSec": 0,
                        "endSec": 4,
                        "sourceRef": "materials/slot-a.wav",
                    },
                    {
                        "id": "vo-slot-b",
                        "startSec": 4,
                        "endSec": 10,
                        "sourceRef": "materials/slot-b.wav",
                    },
                ],
            }
        ],
    }

    specs = collect_voiceover_specs(
        timeline,
        render_root=render_root,
        target_duration_sec=10,
        tts_mode="global",
    )
    assert len(specs) == 2
    assert specs[0][1] == 0.0
    assert specs[1][1] == 4.0
