from __future__ import annotations

from app.perception.analysis_depth import resolve_analysis_depth
from app.perception.keyframe_sampler import select_keyframes_for_llm


def _keyframes(count: int) -> list[dict]:
    return [
        {
            "shotId": f"shot-{index}",
            "timeSec": float(index * 2),
            "path": f"keyframes/frame-{index:03d}.jpg",
            "score": 0.5 + index * 0.001,
        }
        for index in range(count)
    ]


def _shots(count: int) -> list[dict]:
    return [
        {
            "startSec": float(index * 2),
            "endSec": float(index * 2 + 0.8),
            "confidence": 0.95 if index % 5 == 0 else 0.6,
            "changeReason": "histogram_cut",
        }
        for index in range(count)
    ]


def test_sampler_caps_58_frames_to_30_and_keeps_endpoints() -> None:
    keyframes = _keyframes(58)
    shots = _shots(58)
    selected, warnings = select_keyframes_for_llm(
        keyframes,
        shots,
        duration_sec=181.0,
        analysis_depth="standard",
        max_per_video=10,
    )

    assert len(selected) <= 10
    assert selected[0]["timeSec"] == 0.0
    assert selected[-1]["timeSec"] == float(57 * 2)
    assert any("keyframe_sampling_applied" in item for item in warnings)


def test_fast_depth_reduces_cap_via_multiplier(monkeypatch) -> None:
    monkeypatch.setenv("VIDEOMAKER_ANALYSIS_DEPTH", "fast")
    depth = resolve_analysis_depth(
        audio_profile={"metrics": {"voiceoverCoveragePct": 0.95}},
        rhythm_facts={"tempoHint": "fast"},
    )
    assert depth == "fast"

    selected, _ = select_keyframes_for_llm(
        _keyframes(58),
        _shots(58),
        duration_sec=181.0,
        analysis_depth=depth,
    )
    assert len(selected) <= 18


def test_short_shot_merge_reduces_distinct_frames() -> None:
    shots = [
        {"startSec": 0.0, "endSec": 0.5, "confidence": 0.7, "changeReason": "histogram_cut"},
        {"startSec": 0.5, "endSec": 1.0, "confidence": 0.7, "changeReason": "histogram_cut"},
        {"startSec": 1.0, "endSec": 4.0, "confidence": 0.7, "changeReason": "histogram_cut"},
    ]
    keyframes = [
        {"shotId": "shot-0", "timeSec": 0.2, "path": "a.jpg", "score": 0.4},
        {"shotId": "shot-1", "timeSec": 0.7, "path": "b.jpg", "score": 0.9},
        {"shotId": "shot-2", "timeSec": 2.0, "path": "c.jpg", "score": 0.8},
    ]
    selected, _ = select_keyframes_for_llm(
        keyframes,
        shots,
        duration_sec=4.0,
        analysis_depth="standard",
        max_per_video=10,
    )
    assert len(selected) <= 3
    assert len({frame["path"] for frame in selected}) >= 2
