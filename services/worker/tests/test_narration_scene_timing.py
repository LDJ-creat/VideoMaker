from __future__ import annotations

import json
import struct
import wave
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.pipelines.narration_scene_timing import (
    allocate_scene_windows_from_whisper,
    allocate_scene_windows_proportional,
    apply_narration_timing_to_storyboard,
    build_narration_preview,
    build_structure_estimate_preview,
    ensure_narration_preview,
    load_narration_preview,
    narration_content_hash,
    narration_preview_is_current,
    narration_preview_path,
    save_narration_preview,
)
from app.runtime.checkpoint import is_generation_stage_done


def _write_wav(path: Path, *, seconds: float, rate: int = 24000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = int(rate * seconds)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(struct.pack("<h", 0) * frames)


def _structure_three_slots() -> dict:
    return {
        "slots": [
            {"id": "slot-1", "startSec": 0.0, "endSec": 10.0},
            {"id": "slot-2", "startSec": 10.0, "endSec": 20.0},
            {"id": "slot-3", "startSec": 20.0, "endSec": 30.0},
        ]
    }


def test_narration_content_hash_changes_when_master_changes() -> None:
    draft_a = {"masterNarration": "第一句。第二句。", "narrationVoProfile": {"pace": "medium"}}
    draft_b = {"masterNarration": "第一句。第二句！", "narrationVoProfile": {"pace": "medium"}}
    assert narration_content_hash(draft_a) != narration_content_hash(draft_b)


def test_allocate_scene_windows_proportional_scales_to_total() -> None:
    structure = _structure_three_slots()
    windows = allocate_scene_windows_proportional(structure, total_duration_sec=42.0)
    assert len(windows) == 3
    assert windows[0]["slotId"] == "slot-1"
    assert windows[0]["startSec"] == 0.0
    assert windows[-1]["endSec"] == pytest.approx(42.0)
    assert sum(item["endSec"] - item["startSec"] for item in windows) == pytest.approx(42.0)


def test_allocate_scene_windows_from_whisper_maps_segments() -> None:
    structure = _structure_three_slots()
    master = "第一句口播。第二句口播。第三句口播。"
    segments = [
        {"startSec": 0.0, "endSec": 5.0, "text": "第一句口播。"},
        {"startSec": 5.0, "endSec": 12.0, "text": "第二句口播。"},
        {"startSec": 12.0, "endSec": 18.0, "text": "第三句口播。"},
    ]
    windows, method, warnings = allocate_scene_windows_from_whisper(
        master_narration=master,
        structure=structure,
        whisper_segments=segments,
        total_duration_sec=18.0,
    )
    assert method == "whisper"
    assert not warnings
    assert len(windows) == 3
    assert windows[0]["startSec"] == 0.0
    assert windows[-1]["endSec"] == pytest.approx(18.0)
    assert windows[1]["startSec"] >= windows[0]["endSec"] - 0.01


def test_allocate_scene_windows_from_whisper_falls_back_when_empty_segments() -> None:
    structure = _structure_three_slots()
    windows, method, warnings = allocate_scene_windows_from_whisper(
        master_narration="测试口播。",
        structure=structure,
        whisper_segments=[],
        total_duration_sec=9.0,
    )
    assert method == "proportional_fallback"
    assert warnings
    assert windows[-1]["endSec"] == pytest.approx(9.0)


def test_apply_narration_timing_to_storyboard_overwrites_sec() -> None:
    storyboard = [
        {
            "id": "scene-1",
            "slotId": "slot-1",
            "startSec": 0.0,
            "endSec": 10.0,
            "visual": "v",
            "script": "",
            "source": "generated",
        },
        {
            "id": "scene-2",
            "slotId": "slot-2",
            "startSec": 10.0,
            "endSec": 20.0,
            "visual": "v2",
            "script": "",
            "source": "generated",
        },
    ]
    scene_timing = [
        {"slotId": "slot-1", "startSec": 0.0, "endSec": 6.5},
        {"slotId": "slot-2", "startSec": 6.5, "endSec": 12.0},
    ]
    updated = apply_narration_timing_to_storyboard(storyboard, scene_timing)
    assert updated[0]["endSec"] == pytest.approx(6.5)
    assert updated[1]["endSec"] == pytest.approx(12.0)


def test_build_narration_preview_writes_artifact(tmp_path: Path) -> None:
    generation_root = tmp_path / "gen"
    generation_root.mkdir()
    wav_path = generation_root / "preview" / "master.wav"
    _write_wav(wav_path, seconds=6.0)

    preview = build_narration_preview(
        generation_root=generation_root,
        draft={
            "masterNarration": "第一句。第二句。",
            "narrationVoProfile": {"pace": "medium"},
        },
        structure=_structure_three_slots(),
        whisper_segments=[
            {"startSec": 0.0, "endSec": 3.0, "text": "第一句。"},
            {"startSec": 3.0, "endSec": 6.0, "text": "第二句。"},
        ],
        wav_uri="preview/master.wav",
    )
    save_narration_preview(generation_root, preview)
    loaded = load_narration_preview(generation_root)
    assert loaded is not None
    assert loaded["durationSec"] == pytest.approx(6.0)
    assert loaded["alignmentMethod"] == "whisper"
    assert narration_preview_path(generation_root).is_file()


def test_ensure_narration_preview_skips_when_hash_matches(tmp_path: Path) -> None:
    generation_root = tmp_path / "gen"
    generation_root.mkdir()
    draft = {"masterNarration": "测试。", "narrationVoProfile": None}
    preview = {
        "contentHash": narration_content_hash(draft),
        "durationSec": 3.0,
        "wavUri": "preview/master.wav",
        "alignmentMethod": "whisper",
        "sceneTiming": [{"slotId": "slot-1", "startSec": 0.0, "endSec": 3.0}],
        "warnings": [],
        "synthesisSkipped": False,
    }
    save_narration_preview(generation_root, preview)
    _write_wav(generation_root / "preview" / "master.wav", seconds=3.0)

    synthesize = MagicMock()
    transcribe = MagicMock()

    result = ensure_narration_preview(
        generation_root=generation_root,
        draft=draft,
        structure=_structure_three_slots(),
        synthesize_preview=synthesize,
        transcribe_wav=transcribe,
    )
    synthesize.assert_not_called()
    transcribe.assert_not_called()
    assert result["durationSec"] == 3.0


def test_narration_content_hash_includes_tts_options_key() -> None:
    draft = {"masterNarration": "测试口播。", "narrationVoProfile": None}
    prefs_a = {"speaker": "voice-a", "speechRate": 1.0}
    prefs_b = {"speaker": "voice-b", "speechRate": 1.0}
    hash_a = narration_content_hash(draft, workbench_prefs=prefs_a, generation_id="gen-1")
    hash_b = narration_content_hash(draft, workbench_prefs=prefs_b, generation_id="gen-1")
    assert hash_a != hash_b


def test_build_structure_estimate_preview_skips_wav(tmp_path: Path) -> None:
    generation_root = tmp_path / "gen"
    generation_root.mkdir()
    draft = {"masterNarration": "第一句。第二句。", "durationTargetSec": 30.0}
    preview = build_structure_estimate_preview(
        generation_root=generation_root,
        draft=draft,
        structure=_structure_three_slots(),
    )
    assert preview["alignmentMethod"] == "structure_estimate"
    assert preview.get("synthesisSkipped") is True
    assert preview["sceneTiming"]
    assert narration_preview_is_current(generation_root, draft, structure=_structure_three_slots())


def test_is_generation_stage_done_rejects_stale_preview_hash(tmp_path: Path) -> None:
    generation_root = tmp_path / "gen"
    generation_root.mkdir()
    draft = {
        "generationId": "gen-1",
        "masterNarration": "旧口播。",
        "narrationVoProfile": None,
    }
    (generation_root / "script-draft.json").write_text(json.dumps(draft), encoding="utf-8")
    stale_preview = {
        "contentHash": narration_content_hash({"masterNarration": "新口播。", "narrationVoProfile": None}),
        "durationSec": 3.0,
        "wavUri": "preview/master.wav",
        "alignmentMethod": "whisper",
        "sceneTiming": [{"slotId": "slot-1", "startSec": 0.0, "endSec": 3.0}],
        "warnings": [],
        "synthesisSkipped": False,
    }
    save_narration_preview(generation_root, stale_preview)
    _write_wav(generation_root / "preview" / "master.wav", seconds=3.0)
    assert is_generation_stage_done("narration_preview", generation_root) is False
