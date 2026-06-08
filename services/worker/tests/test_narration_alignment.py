from __future__ import annotations

import struct
import wave
from pathlib import Path

import pytest

from app.pipelines.narration_alignment import (
    align_subtitles_to_voiceover,
    chunk_subtitle_text,
    strip_placeholder_subtitles,
    subtitle_time_windows,
    wav_duration_sec,
)


def _write_wav(path: Path, *, seconds: float, rate: int = 24000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = int(rate * seconds)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(struct.pack("<h", 0) * frames)


def test_wav_duration_sec_reads_file(tmp_path: Path) -> None:
    wav_path = tmp_path / "sample.wav"
    _write_wav(wav_path, seconds=6.0)
    assert wav_duration_sec(wav_path) == 6.0


def test_subtitle_windows_cover_audible_range() -> None:
    windows = subtitle_time_windows(0.0, 6.0, ["第一句。", "第二句。"])
    assert windows[0][0] == 0.0
    assert windows[-1][1] == 6.0


def test_align_subtitles_uses_shorter_wav_window(tmp_path: Path) -> None:
    render_root = tmp_path / "render"
    materials = render_root / "materials"
    _write_wav(materials / "slot-a.wav", seconds=6.0)

    timeline = {
        "durationSec": 10.0,
        "tracks": [
            {
                "id": "track-text",
                "type": "text",
                "clips": [
                    {
                        "id": "subtitle-slot-a",
                        "startSec": 0.0,
                        "endSec": 10.0,
                        "content": "占位",
                        "styleRef": "style://subtitle/clean",
                    }
                ],
            },
            {
                "id": "track-voiceover",
                "type": "voiceover",
                "clips": [
                    {
                        "id": "vo-slot-a",
                        "startSec": 0.0,
                        "endSec": 6.0,
                        "sourceRef": "materials/slot-a.wav",
                    }
                ],
            },
        ],
    }
    storyboard = [
        {
            "id": "scene-a",
            "slotId": "slot-a",
            "startSec": 0.0,
            "endSec": 10.0,
            "script": "第一句口播。第二句口播。",
        }
    ]

    updated = align_subtitles_to_voiceover(
        timeline,
        storyboard,
        {"subtitle": {"preset": "clean"}},
        render_root,
    )
    text_track = next(t for t in updated["tracks"] if t["type"] == "text")
    subtitles = [c for c in text_track["clips"] if str(c["id"]).startswith("subtitle-slot-a")]
    assert len(subtitles) >= 2
    assert subtitles[-1]["endSec"] <= 6.0
    assert subtitles[-1]["endSec"] == 6.0


def test_align_subtitles_matches_clamped_voiceover(tmp_path: Path) -> None:
    render_root = tmp_path / "render"
    materials = render_root / "materials"
    _write_wav(materials / "slot-b.wav", seconds=10.0)

    timeline = {
        "durationSec": 5.0,
        "tracks": [
            {"id": "track-text", "type": "text", "clips": []},
            {
                "id": "track-voiceover",
                "type": "voiceover",
                "clips": [
                    {
                        "id": "vo-slot-b",
                        "startSec": 0.0,
                        "endSec": 5.0,
                        "sourceRef": "materials/slot-b.wav",
                    }
                ],
            },
        ],
    }
    storyboard = [
        {
            "id": "scene-b",
            "slotId": "slot-b",
            "startSec": 0.0,
            "endSec": 5.0,
            "script": "被截断的口播文案。",
        }
    ]

    updated = align_subtitles_to_voiceover(
        timeline,
        storyboard,
        {"subtitle": {"preset": "clean"}},
        render_root,
    )
    clip = next(
        c
        for c in next(t for t in updated["tracks"] if t["type"] == "text")["clips"]
        if c["id"] == "subtitle-slot-b"
    )
    assert clip["startSec"] == 0.0
    assert clip["endSec"] == 5.0


def test_align_subtitles_global_master(tmp_path: Path) -> None:
    render_root = tmp_path / "render"
    _write_wav(render_root / "materials" / "master.wav", seconds=8.0)

    timeline = {
        "durationSec": 5.0,
        "tracks": [
            {"id": "track-text", "type": "text", "clips": []},
            {
                "id": "track-voiceover",
                "type": "voiceover",
                "clips": [
                    {
                        "id": "vo-master",
                        "startSec": 0.0,
                        "endSec": 8.0,
                        "sourceRef": "materials/master.wav",
                    }
                ],
            },
        ],
    }

    updated = align_subtitles_to_voiceover(
        timeline,
        [],
        {"subtitle": {"preset": "clean"}},
        render_root,
        master_narration="全片口播第一句。第二句结束。",
        tts_mode="global",
    )
    subtitles = [
        c
        for c in next(t for t in updated["tracks"] if t["type"] == "text")["clips"]
        if str(c["id"]).startswith("subtitle-master")
    ]
    assert subtitles
    assert subtitles[-1]["endSec"] == 8.0


def test_strip_placeholder_subtitles() -> None:
    timeline = {
        "tracks": [
            {
                "id": "track-text",
                "type": "text",
                "clips": [
                    {"id": "subtitle-slot-1", "startSec": 0, "endSec": 1, "content": "x"},
                    {"id": "clip-slot-1", "startSec": 0, "endSec": 1, "content": "y"},
                ],
            }
        ]
    }
    stripped = strip_placeholder_subtitles(timeline)
    clips = stripped["tracks"][0]["clips"]
    assert len(clips) == 1
    assert clips[0]["id"] == "clip-slot-1"


def test_chunk_subtitle_text_splits_sentences() -> None:
    chunks = chunk_subtitle_text("你好。世界！")
    assert len(chunks) == 2


def test_wav_duration_sec_falls_back_when_header_corrupt(tmp_path: Path) -> None:
    wav_path = tmp_path / "corrupt-header.wav"
    _write_wav(wav_path, seconds=2.0, rate=48000)
    data = bytearray(wav_path.read_bytes())
    struct.pack_into("<I", data, 40, 1_073_741_773)
    corrupt_path = tmp_path / "corrupt-header-patched.wav"
    corrupt_path.write_bytes(data)
    assert wav_duration_sec(corrupt_path) == pytest.approx(2.0, rel=0.05)
