from __future__ import annotations

import io
import struct
import wave
from pathlib import Path
from unittest.mock import MagicMock

from app.pipelines.tts_synthesis import synthesize_master_wav
from app.pipelines.tts_voice_options import build_tts_synthesis_options, normalize_vo_directive
from app.tools.tts_tool import TTSTool


def _workbench() -> dict:
    return {
        "resourceId": "seed-tts-2.0",
        "speaker": "zh_female_vv_uranus_bigtts",
        "modelVariant": "seed-tts-2.0-expressive",
        "speechRate": 0,
        "loudnessRate": 0,
        "emotion": None,
        "emotionScale": 4,
        "contextTexts": "句末收束",
        "explicitLanguage": "zh",
        "format": "pcm",
        "sampleRate": 24000,
        "chunkCharLimit": 400,
    }


def _wav_bytes(*, frames: int = 2400, sample_rate: int = 24000) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(struct.pack("<h", 0) * frames)
    return buffer.getvalue()


def test_build_tts_synthesis_options_scene_overrides_narration_and_sample() -> None:
    structure = {
        "audio": {
            "voProfile": {
                "pace": "medium",
                "persona": "科普博主",
            }
        }
    }
    options = build_tts_synthesis_options(
        structure=structure,
        workbench_prefs=_workbench(),
        generation_id="gen-1",
        narration_vo_profile={"energy": "high"},
        scene_vo_directive={"pace": "fast", "emotion": "happy", "contextHint": "疑问句上扬"},
    )
    assert options["speechRate"] == 30
    assert options["emotion"] == "happy"
    assert "疑问句上扬" in options["contextTexts"]
    assert "更有感染力" in options["contextTexts"]
    assert "科普博主" in options["contextTexts"]


def test_normalize_vo_directive_rejects_invalid_pace() -> None:
    normalized, warnings = normalize_vo_directive({"pace": "turbo", "persona": "主播"})
    assert normalized == {"persona": "主播"}
    assert warnings


def test_synthesize_master_wav_single_call_when_directives_match(tmp_path: Path) -> None:
    gateway = MagicMock()
    gateway.synthesize_speech.return_value = _wav_bytes()
    tool = TTSTool(gateway=gateway)
    storyboard = [
        {
            "slotId": "slot-a",
            "script": "第一句。",
            "voDirective": {"pace": "medium"},
        },
        {
            "slotId": "slot-b",
            "script": "第二句。",
            "voDirective": {"pace": "medium"},
        },
    ]
    output_path = tmp_path / "master.wav"
    synthesize_master_wav(
        tool=tool,
        master_narration="第一句。第二句。",
        storyboard=storyboard,
        structure={},
        workbench_prefs=_workbench(),
        generation_id="gen-1",
        narration_vo_profile=None,
        output_path=output_path,
    )
    assert output_path.is_file()
    gateway.synthesize_speech.assert_called_once()


def test_synthesize_master_wav_segments_when_directives_differ(tmp_path: Path) -> None:
    gateway = MagicMock()
    gateway.synthesize_speech.side_effect = [
        _wav_bytes(frames=1200),
        _wav_bytes(frames=2400),
    ]
    tool = TTSTool(gateway=gateway)
    storyboard = [
        {"slotId": "slot-a", "script": "快一点。", "voDirective": {"pace": "fast"}},
        {"slotId": "slot-b", "script": "慢一点。", "voDirective": {"pace": "slow"}},
    ]
    output_path = tmp_path / "master.wav"
    synthesize_master_wav(
        tool=tool,
        master_narration="快一点。慢一点。",
        storyboard=storyboard,
        structure={},
        workbench_prefs=_workbench(),
        generation_id="gen-1",
        narration_vo_profile=None,
        output_path=output_path,
    )
    assert gateway.synthesize_speech.call_count == 2
    with wave.open(str(output_path), "rb") as handle:
        assert handle.getnframes() == 3600


def test_synthesize_master_wav_sanitizes_unsafe_slot_id_in_temp_path(tmp_path: Path) -> None:
    gateway = MagicMock()
    gateway.synthesize_speech.return_value = _wav_bytes(frames=1200)
    tool = TTSTool(gateway=gateway)
    storyboard = [
        {"slotId": "../evil", "script": "第一段。", "voDirective": {"pace": "fast"}},
        {"slotId": "slot-b", "script": "第二段。", "voDirective": {"pace": "slow"}},
    ]
    output_path = tmp_path / "master.wav"
    synthesize_master_wav(
        tool=tool,
        master_narration="第一段。第二段。",
        storyboard=storyboard,
        structure={},
        workbench_prefs=_workbench(),
        generation_id="gen-1",
        narration_vo_profile=None,
        output_path=output_path,
    )
    assert not (tmp_path / ".segment-..").exists()
    assert gateway.synthesize_speech.call_count == 2