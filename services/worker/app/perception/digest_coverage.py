from __future__ import annotations

from typing import Any


def _segment_bounds(segment: dict[str, Any]) -> tuple[float, float]:
    start = float(segment.get("startSec", 0.0))
    end = float(segment.get("endSec", start))
    if end < start:
        end = start
    return start, end


def _digest_bounds(digest: dict[str, Any]) -> tuple[float, float]:
    start = float(digest.get("startSec", 0.0))
    end = float(digest.get("endSec", start))
    if end < start:
        end = start
    return start, end


def segment_digest_coverage(segment: dict[str, Any], digests: list[dict[str, Any]]) -> float:
    seg_start, seg_end = _segment_bounds(segment)
    seg_duration = seg_end - seg_start
    if seg_duration <= 0:
        return 1.0 if digests else 0.0

    covered = 0.0
    for digest in digests:
        if not isinstance(digest, dict):
            continue
        d_start, d_end = _digest_bounds(digest)
        overlap_start = max(seg_start, d_start)
        overlap_end = min(seg_end, d_end)
        if overlap_end > overlap_start:
            covered += overlap_end - overlap_start

    return min(1.0, covered / seg_duration)


def digests_cover_segment(
    segment: dict[str, Any],
    digests: list[dict[str, Any]],
    *,
    min_ratio: float = 0.6,
) -> bool:
    return segment_digest_coverage(segment, digests) >= min_ratio


def resolve_segment_vision_policy(
    segment: dict[str, Any],
    analysis: dict[str, Any],
) -> tuple[bool, int]:
    from app.agents.structure_inputs import compute_rhythm_facts
    from app.perception.analysis_depth import (
        resolve_analysis_depth,
        segment_vision_max_keyframes,
        segment_vision_min_coverage,
    )

    shots = list(analysis.get("shots") or [])
    metadata = analysis.get("metadata") or {}
    duration_sec = float(metadata.get("durationSec") or 0.0)
    rhythm_facts = compute_rhythm_facts(shots, duration_sec=duration_sec)
    audio_profile = analysis.get("audioProfile")
    depth = analysis.get("analysisDepth")
    if depth not in {"fast", "standard", "deep"}:
        depth = resolve_analysis_depth(
            audio_profile=audio_profile if isinstance(audio_profile, dict) else None,
            rhythm_facts=rhythm_facts,
        )

    digests = list(analysis.get("keyframeBatchDigests") or [])
    if depth == "deep":
        return True, segment_vision_max_keyframes(depth, use_vision=True)
    if digests and digests_cover_segment(
        segment,
        digests,
        min_ratio=segment_vision_min_coverage(),
    ):
        return False, 0
    return True, segment_vision_max_keyframes(depth, use_vision=True)
