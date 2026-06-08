from __future__ import annotations

from dataclasses import replace
from typing import Any

from app.render.timeline_compiler.scene_segments import SceneSegment


def apply_hold_tail_to_segments(
    segments: list[SceneSegment],
    target_duration_sec: float,
) -> list[SceneSegment]:
    if not segments or target_duration_sec <= 0:
        return segments
    updated = list(segments)
    last = updated[-1]
    if target_duration_sec > last.end_sec + 0.01:
        updated[-1] = replace(last, end_sec=float(target_duration_sec))
    return updated


def timeline_target_duration(timeline: dict[str, Any], segments: list[SceneSegment]) -> float:
    duration = float(timeline.get("durationSec") or 0.0)
    if duration > 0:
        return duration
    if not segments:
        return 0.0
    return max(segment.end_sec for segment in segments)
