from __future__ import annotations

import struct
import wave
from pathlib import Path

import pytest

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


def test_hold_tail_syncs_inverted_clip_times_on_early_return(tmp_path: Path) -> None:
    render_root = tmp_path / "render"
    _write_wav(render_root / "materials" / "master.wav", seconds=34.316)

    plan = {
        "ttsMode": "global",
        "generationStrategy": "long_form_composed",
        "storyboard": [
            {
                "id": "scene-6",
                "slotId": "slot-6",
                "startSec": 21.4,
                "endSec": 24.2,
                "script": "center scene",
                "visual": "generated/action-slot-6.mp4",
                "source": "generated",
            },
        ],
        "timeline": {
            "durationSec": 34.316,
            "tracks": [
                {
                    "id": "track-video",
                    "type": "video",
                    "clips": [
                        {
                            "id": "clip-slot-6",
                            "startSec": 41.325,
                            "endSec": 34.316,
                            "sourceRef": "generated/action-slot-6.mp4",
                        }
                    ],
                },
                {
                    "id": "track-voiceover",
                    "type": "voiceover",
                    "clips": [
                        {
                            "id": "vo-master",
                            "startSec": 0.0,
                            "endSec": 34.316,
                            "sourceRef": "materials/master.wav",
                        }
                    ],
                },
            ],
        },
    }

    updated = sync_timeline_to_narration(plan, render_root=render_root, mode="hold_tail")
    clip = next(
        clip
        for track in updated["timeline"]["tracks"]
        if track["type"] == "video"
        for clip in track["clips"]
        if clip["id"] == "clip-slot-6"
    )
    assert clip["startSec"] == pytest.approx(21.4, abs=0.001)
    assert clip["endSec"] == pytest.approx(24.2, abs=0.001)
    assert clip["startSec"] < clip["endSec"]


def test_refresh_timeline_clip_timing_without_narration_wav() -> None:
    from app.pipelines.narration_timeline import refresh_timeline_clip_timing

    plan = {
        "storyboard": [
            {
                "id": "scene-slot-6",
                "slotId": "slot-6",
                "startSec": 21.409,
                "endSec": 24.171,
            }
        ],
        "timeline": {
            "durationSec": 34.316,
            "tracks": [
                {
                    "id": "track-video",
                    "type": "video",
                    "clips": [
                        {
                            "id": "clip-slot-6",
                            "startSec": 41.325,
                            "endSec": 34.316,
                            "sourceRef": "materials/action-slot-6.mp4",
                        }
                    ],
                }
            ],
        },
    }

    updated = refresh_timeline_clip_timing(plan)
    clip = updated["timeline"]["tracks"][0]["clips"][0]
    assert clip["startSec"] == pytest.approx(21.409, abs=0.001)
    assert clip["endSec"] == pytest.approx(24.171, abs=0.001)


def test_hold_tail_auto_global_ripple_when_preview_deviation_exceeds_threshold(tmp_path: Path) -> None:
    render_root = tmp_path / "render"
    _write_wav(render_root / "materials" / "master.wav", seconds=12.0)

    plan = {
        "ttsMode": "global",
        "generationStrategy": "long_form_composed",
        "narrationPreviewDurationSec": 10.0,
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
    assert updated["storyboard"][0]["endSec"] == pytest.approx(9.6)
    assert updated["storyboard"][1]["endSec"] == 12.0


def test_global_proportional_scale_resizes_all_scenes(tmp_path: Path) -> None:
    render_root = tmp_path / "render"
    _write_wav(render_root / "materials" / "master.wav", seconds=15.0)

    plan = {
        "ttsMode": "global",
        "narrationPreviewDurationSec": 10.0,
        "storyboard": [
            {
                "id": "scene-1",
                "slotId": "slot-1",
                "startSec": 0.0,
                "endSec": 5.0,
                "script": "a",
                "visual": "v",
                "source": "generated",
            },
            {
                "id": "scene-2",
                "slotId": "slot-2",
                "startSec": 5.0,
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
                        {"id": "clip-slot-1", "startSec": 0.0, "endSec": 5.0},
                        {"id": "clip-slot-2", "startSec": 5.0, "endSec": 10.0},
                    ],
                },
                {
                    "id": "track-voiceover",
                    "type": "voiceover",
                    "clips": [
                        {
                            "id": "vo-master",
                            "startSec": 0.0,
                            "endSec": 15.0,
                            "sourceRef": "materials/master.wav",
                        }
                    ],
                },
            ],
        },
    }

    updated = sync_timeline_to_narration(plan, render_root=render_root, mode="global_ripple")
    assert updated["narrationDurationSec"] == 15.0
    assert updated["storyboard"][0]["endSec"] == pytest.approx(7.5)
    assert updated["storyboard"][1]["endSec"] == 15.0


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


def test_global_ripple_eliminates_overlapping_storyboard_windows(tmp_path: Path) -> None:
    """Regression: scaled storyboard must not overlap when narration_end < planned span."""
    render_root = tmp_path / "render"
    _write_wav(render_root / "materials" / "master.wav", seconds=30.8)

    storyboard = [
        {"id": "scene-1", "slotId": "slot-1", "startSec": 0.0, "endSec": 5.0, "script": "a", "visual": "v", "source": "generated"},
        {"id": "scene-2", "slotId": "slot-2", "startSec": 5.0, "endSec": 10.0, "script": "b", "visual": "v", "source": "generated"},
        {"id": "scene-3", "slotId": "slot-3", "startSec": 10.0, "endSec": 15.0, "script": "c", "visual": "v", "source": "generated"},
        {"id": "scene-4", "slotId": "slot-4", "startSec": 15.0, "endSec": 20.0, "script": "d", "visual": "v", "source": "generated"},
        {"id": "scene-5", "slotId": "slot-5", "startSec": 20.0, "endSec": 32.895, "script": "e", "visual": "v", "source": "generated"},
        {"id": "scene-6", "slotId": "slot-6", "startSec": 30.8, "endSec": 35.0, "script": "f", "visual": "v", "source": "generated"},
    ]
    plan = {
        "ttsMode": "global",
        "generationStrategy": "long_form_composed",
        "storyboard": storyboard,
        "timeline": {
            "durationSec": 35.0,
            "tracks": [
                {
                    "id": "track-video",
                    "type": "video",
                    "clips": [
                        {"id": f"clip-{scene['slotId']}", "startSec": scene["startSec"], "endSec": scene["endSec"]}
                        for scene in storyboard
                    ],
                },
                {
                    "id": "track-voiceover",
                    "type": "voiceover",
                    "clips": [
                        {
                            "id": "vo-master",
                            "startSec": 0.0,
                            "endSec": 30.8,
                            "sourceRef": "materials/master.wav",
                        }
                    ],
                },
            ],
        },
    }

    updated = sync_timeline_to_narration(plan, render_root=render_root, mode="global_ripple")
    assert updated["timeline"]["durationSec"] == pytest.approx(30.8, abs=0.05)
    scenes = sorted(updated["storyboard"], key=lambda item: float(item["startSec"]))
    assert scenes[-1]["endSec"] == pytest.approx(30.8, abs=0.05)
    for prev, current in zip(scenes, scenes[1:]):
        assert current["startSec"] >= prev["endSec"] - 0.001
        assert current["endSec"] > current["startSec"]
