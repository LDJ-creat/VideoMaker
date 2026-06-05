from __future__ import annotations

import os
import re
import subprocess
from typing import Any

import librosa
import numpy as np

_SILENCE_START = re.compile(
    r"silence_start:\s*(?P<start>[0-9.]+)",
    re.IGNORECASE,
)
_SILENCE_END = re.compile(
    r"silence_end:\s*(?P<end>[0-9.]+)",
    re.IGNORECASE,
)
_DEFAULT_FRAME_SEC = 0.1
_SPEECH_PAD_SEC = 0.15
_ENERGY_FLOOR_DB = -42.0


def _round_sec(value: float) -> float:
    return round(float(value), 3)


def _detect_silence_regions_ffmpeg(audio_path: str, *, duration_sec: float) -> list[dict[str, float]]:
    command = [
        "ffmpeg",
        "-hide_banner",
        "-i",
        audio_path,
        "-af",
        "silencedetect=noise=-35dB:d=0.25",
        "-f",
        "null",
        "-",
    ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return []

    stderr = result.stderr or ""
    regions: list[dict[str, float]] = []
    open_start: float | None = None
    for line in stderr.splitlines():
        start_match = _SILENCE_START.search(line)
        if start_match:
            open_start = float(start_match.group("start"))
            continue
        end_match = _SILENCE_END.search(line)
        if end_match and open_start is not None:
            end_sec = float(end_match.group("end"))
            regions.append({"startSec": _round_sec(open_start), "endSec": _round_sec(end_sec)})
            open_start = None
    if open_start is not None and duration_sec > open_start:
        regions.append({"startSec": _round_sec(open_start), "endSec": _round_sec(duration_sec)})
    return regions


def _speech_regions_from_transcript(transcript: dict[str, Any] | list[Any]) -> list[dict[str, Any]]:
    segments = transcript if isinstance(transcript, list) else transcript.get("segments", [])
    regions: list[dict[str, Any]] = []
    for segment in segments:
        if not isinstance(segment, dict):
            continue
        text = str(segment.get("text", "")).strip()
        if not text:
            continue
        regions.append(
            {
                "startSec": _round_sec(float(segment.get("startSec", 0.0))),
                "endSec": _round_sec(float(segment.get("endSec", 0.0))),
                "textPreview": text[:40],
            }
        )
    return regions


def _overlaps(left_start: float, left_end: float, right_start: float, right_end: float) -> bool:
    return left_start < right_end and right_end > right_start


def _compute_bgm_candidates(
    *,
    duration_sec: float,
    speech_regions: list[dict[str, Any]],
    energy_timeline: list[dict[str, float]],
    silence_regions: list[dict[str, float]],
) -> list[dict[str, float]]:
    candidates: list[dict[str, float]] = []
    if not energy_timeline:
        return candidates

    threshold = _ENERGY_FLOOR_DB
    window_start: float | None = None
    for index, point in enumerate(energy_timeline):
        time_sec = float(point["timeSec"])
        rms_db = float(point["rmsDb"])
        in_speech = any(
            _overlaps(
                time_sec,
                time_sec + _DEFAULT_FRAME_SEC,
                float(region["startSec"]),
                float(region["endSec"]),
            )
            for region in speech_regions
        )
        in_silence = any(
            _overlaps(
                time_sec,
                time_sec + _DEFAULT_FRAME_SEC,
                float(region["startSec"]),
                float(region["endSec"]),
            )
            for region in silence_regions
        )
        active = rms_db >= threshold and not in_speech and not in_silence
        if active and window_start is None:
            window_start = time_sec
        if (not active or index == len(energy_timeline) - 1) and window_start is not None:
            end_sec = time_sec if not active else duration_sec
            if end_sec - window_start >= 0.4:
                candidates.append({"startSec": _round_sec(window_start), "endSec": _round_sec(end_sec)})
            window_start = None
    return candidates


def analyze_audio_profile(
    audio_path: str,
    *,
    transcript: dict[str, Any] | list[Any],
    duration_sec: float,
    frame_sec: float = _DEFAULT_FRAME_SEC,
) -> dict[str, Any]:
    speech_regions = _speech_regions_from_transcript(transcript)
    silence_regions = _detect_silence_regions_ffmpeg(audio_path, duration_sec=duration_sec)

    y, sr = librosa.load(audio_path, sr=None, mono=True)
    if duration_sec <= 0 and len(y) > 0 and sr > 0:
        duration_sec = float(len(y) / sr)

    hop_length = max(1, int(sr * frame_sec))
    rms = librosa.feature.rms(y=y, hop_length=hop_length)[0]
    rms_db = librosa.amplitude_to_db(rms, ref=np.max).astype(float)
    times = librosa.frames_to_time(np.arange(len(rms_db)), sr=sr, hop_length=hop_length)
    energy_timeline = [
        {"timeSec": _round_sec(float(time_sec)), "rmsDb": round(float(db), 2)}
        for time_sec, db in zip(times, rms_db, strict=False)
    ]

    onset_frames = librosa.onset.onset_detect(y=y, sr=sr, hop_length=hop_length, units="time")
    onset_times = [_round_sec(float(value)) for value in onset_frames]

    tempo_bpm: float | None = None
    try:
        tempo_estimate = librosa.beat.beat_track(y=y, sr=sr, hop_length=hop_length)[0]
        if isinstance(tempo_estimate, np.ndarray):
            tempo_bpm = round(float(tempo_estimate[0]), 2) if tempo_estimate.size else None
        else:
            tempo_bpm = round(float(tempo_estimate), 2)
    except Exception:
        tempo_bpm = None

    speech_duration = sum(
        float(region["endSec"]) - float(region["startSec"]) for region in speech_regions
    )
    silence_duration = sum(
        float(region["endSec"]) - float(region["startSec"]) for region in silence_regions
    )
    total = max(duration_sec, 0.001)
    bgm_candidates = _compute_bgm_candidates(
        duration_sec=total,
        speech_regions=speech_regions,
        energy_timeline=energy_timeline,
        silence_regions=silence_regions,
    )

    return {
        "hasVoiceover": bool(speech_regions),
        "hasBgm": bool(bgm_candidates),
        "silenceRegions": silence_regions,
        "speechRegions": speech_regions,
        "bgmCandidateRegions": bgm_candidates,
        "energyTimeline": energy_timeline,
        "onsetTimes": onset_times,
        "tempoBpm": tempo_bpm,
        "metrics": {
            "voiceoverCoveragePct": round(min(1.0, speech_duration / total), 3),
            "silenceCoveragePct": round(min(1.0, silence_duration / total), 3),
            "bgmBedLikely": bool(bgm_candidates) and (speech_duration / total) > 0.2,
        },
    }


def build_audio_profile(
    audio_path: str | None,
    *,
    transcript: dict[str, Any] | list[Any],
    duration_sec: float,
) -> dict[str, Any] | None:
    if audio_path is None or not os.path.isfile(audio_path):
        return None
    return analyze_audio_profile(
        audio_path,
        transcript=transcript,
        duration_sec=duration_sec,
    )
