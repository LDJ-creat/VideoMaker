from __future__ import annotations

import os
from typing import Any, Literal

AnalysisDepth = Literal["fast", "standard", "deep"]


def _env_depth() -> str:
    return os.environ.get("VIDEOMAKER_ANALYSIS_DEPTH", "auto").strip().lower()


def resolve_analysis_depth(
    *,
    audio_profile: dict[str, Any] | None = None,
    rhythm_facts: dict[str, Any] | None = None,
) -> AnalysisDepth:
    configured = _env_depth()
    if configured in {"fast", "standard", "deep"}:
        return configured  # type: ignore[return-value]

    metrics = (audio_profile or {}).get("metrics") or {}
    voiceover_pct = float(metrics.get("voiceoverCoveragePct") or 0.0)
    tempo_hint = str((rhythm_facts or {}).get("tempoHint") or "")
    if voiceover_pct >= 0.85 and tempo_hint in {"fast", "mixed"}:
        return "fast"
    return "standard"


def keyframe_cap_multiplier(depth: AnalysisDepth) -> float:
    if depth == "fast":
        return 0.6
    if depth == "deep":
        return 1.5
    return 1.0


def default_max_keyframes_per_video(duration_sec: float, depth: AnalysisDepth) -> int:
    raw = os.environ.get("VIDEOMAKER_KEYFRAME_MAX_PER_VIDEO", "").strip()
    if raw:
        try:
            return max(1, int(raw))
        except ValueError:
            pass
    base = min(30, max(12, round(duration_sec / 6)))
    if depth == "deep":
        return 45
    scaled = int(round(base * keyframe_cap_multiplier(depth)))
    return max(12, scaled)


def default_vision_batch_max_calls(depth: AnalysisDepth) -> int:
    raw = os.environ.get("VIDEOMAKER_VISION_BATCH_MAX_CALLS", "").strip()
    if raw:
        try:
            return max(1, int(raw))
        except ValueError:
            pass
    if depth == "fast":
        return 4
    if depth == "deep":
        return 8
    return 6


def segment_vision_min_coverage() -> float:
    raw = os.environ.get("VIDEOMAKER_SEGMENT_VISION_MIN_COVERAGE", "0.6").strip()
    try:
        return max(0.0, min(1.0, float(raw)))
    except ValueError:
        return 0.6


def segment_vision_max_keyframes(depth: AnalysisDepth, *, use_vision: bool) -> int:
    if not use_vision:
        return 0
    if depth == "fast":
        return 2
    if depth == "deep":
        return 8
    return 8
