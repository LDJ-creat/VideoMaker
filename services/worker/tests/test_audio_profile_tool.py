from __future__ import annotations

import numpy as np
import soundfile as sf

from app.tools.audio_profile_tool import analyze_audio_profile


def _write_tone_wav(path, *, duration_sec: float = 2.0, sr: int = 16000) -> None:
    t = np.linspace(0, duration_sec, int(sr * duration_sec), endpoint=False)
    signal = 0.2 * np.sin(2 * np.pi * 440 * t)
    sf.write(path, signal, sr)


def test_analyze_audio_profile_detects_speech_and_silence(tmp_path) -> None:
    wav_path = tmp_path / "tone.wav"
    _write_tone_wav(wav_path, duration_sec=3.0)

    transcript = {
        "segments": [
            {"startSec": 0.2, "endSec": 1.0, "text": "还在花冤枉钱"},
            {"startSec": 1.5, "endSec": 2.4, "text": "试试这个方案"},
        ]
    }
    profile = analyze_audio_profile(str(wav_path), transcript=transcript, duration_sec=3.0)

    assert profile["hasVoiceover"] is True
    assert profile["metrics"]["voiceoverCoveragePct"] > 0
    assert isinstance(profile["energyTimeline"], list) and profile["energyTimeline"]
    assert isinstance(profile["onsetTimes"], list)
    assert len(profile["speechRegions"]) == 2


def test_build_audio_profile_returns_none_for_missing_file(tmp_path) -> None:
    from app.tools.audio_profile_tool import build_audio_profile

    assert build_audio_profile(str(tmp_path / "missing.wav"), transcript=[], duration_sec=0.0) is None
