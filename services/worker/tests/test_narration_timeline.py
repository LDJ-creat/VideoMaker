from __future__ import annotations

import struct
import wave
from pathlib import Path

from app.pipelines.narration_timeline import (
    narration_end_sec,
    sync_timeline_to_narration,
)


def _write_wav(path: Path, *, seconds: float, rate: int = 24000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = int(rate * seconds)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(struct.pack("<h", 0) * frames)


def test_hold_tail_extends_last_scene_and_duration(tmp_path: Path) -> None:
    render_root = tmp_path / "render"
    _write_wav(render_root / "materials" / "master.wav", seconds=12.0)

    plan = {
        "ttsMode": "global",
        "generationStrategy": "long_form_composed",
        "storyboard": [
            {
                "id": "scene-1",
                "slotId": "slot-1",
                "startSec": 0.0,
                "endSec": 8.0,
                "script": "a",
                "visual": "v",
                "source": "generated",
            },
            {
                "id": "scene-2",
                "slotId": "slot-2",
                "startSec": 8.0,
                "endSec": 10.0,
                "script": "b",
                "visual": "v2",
                "source": "generated",
            },
        ],
        "timeline": {
            "durationSec": 10.0,
            "tracks": [
                {
                    "id": "track-video",
                    "type": "video",
                    "clips": [
                        {"id": "clip-slot-1", "startSec": 0.0, "endSec": 8.0},
                        {"id": "clip-slot-2", "startSec": 8.0, "endSec": 10.0},
                    ],
                },
                {
                    "id": "track-voiceover",
                    "type": "voiceover",
                    "clips": [
                        {
                            "id": "vo-master",
                            "startSec": 0.0,
                            "endSec": 12.0,
                            "sourceRef": "materials/master.wav",
                        }
                    ],
                },
            ],
        },
    }

    updated = sync_timeline_to_narration(plan, render_root=render_root, mode="hold_tail")
    assert updated["narrationDurationSec"] == 12.0
    assert updated["timeline"]["durationSec"] == 12.0
    last_scene = updated["storyboard"][-1]
    assert last_scene["endSec"] == 12.0
    video_clips = next(t for t in updated["timeline"]["tracks"] if t["type"] == "video")["clips"]
    assert video_clips[-1]["endSec"] == 12.0


def test_ripple_overflow_shifts_following_scenes(tmp_path: Path) -> None:
    """Ripple helper shifts scenes when per-slot wav exceeds planned window."""
    from app.pipelines.narration_timeline import _ripple_scene_timing

    render_root = tmp_path / "render"
    _write_wav(render_root / "materials" / "slot-1.wav", seconds=5.0)

    storyboard = [
        {
            "id": "scene-1",
            "slotId": "slot-1",
            "startSec": 0.0,
            "endSec": 3.0,
            "script": "a",
            "visual": "v",
            "source": "generated",
        },
        {
            "id": "scene-2",
            "slotId": "slot-2",
            "startSec": 3.0,
            "endSec": 6.0,
            "script": "b",
            "visual": "v2",
            "source": "generated",
        },
    ]
    vo_clips = {
        "vo-slot-1": {
            "id": "vo-slot-1",
            "startSec": 0.0,
            "endSec": 3.0,
            "sourceRef": "materials/slot-1.wav",
        }
    }
    rippled = _ripple_scene_timing(storyboard, render_root=render_root, vo_clips=vo_clips)
    assert rippled[0]["endSec"] == 5.0
    assert rippled[1]["startSec"] == 5.0
    assert rippled[1]["endSec"] == 8.0


def test_narration_end_sec_global_master(tmp_path: Path) -> None:
    render_root = tmp_path / "render"
    _write_wav(render_root / "materials" / "master.wav", seconds=7.5)
    plan = {
        "ttsMode": "global",
        "timeline": {
            "tracks": [
                {
                    "type": "voiceover",
                    "clips": [
                        {
                            "id": "vo-master",
                            "sourceRef": "materials/master.wav",
                            "startSec": 0,
                            "endSec": 7.5,
                        }
                    ],
                }
            ]
        },
    }
    assert narration_end_sec(plan, render_root=render_root) == 7.5
