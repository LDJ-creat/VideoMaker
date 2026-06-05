from __future__ import annotations

import os
from typing import Any

from app.agents.structure_inputs import _evenly_sample, _pick_best_keyframes_per_shot
from app.perception.analysis_depth import AnalysisDepth, default_max_keyframes_per_video


def _shot_merge_max_sec() -> float:
    raw = os.environ.get("VIDEOMAKER_SHOT_MERGE_MAX_SEC", "1.0").strip()
    try:
        return max(0.1, float(raw))
    except ValueError:
        return 1.0


def _shot_duration(shot: dict[str, Any]) -> float:
    return float(shot.get("endSec", 0.0)) - float(shot.get("startSec", 0.0))


def _shot_index_from_id(shot_id: str) -> int | None:
    if not shot_id.startswith("shot-"):
        return None
    suffix = shot_id.removeprefix("shot-")
    return int(suffix) if suffix.isdigit() else None


def _merge_shot_groups(shots: list[dict[str, Any]]) -> list[list[int]]:
    if not shots:
        return []
    merge_max = _shot_merge_max_sec()
    max_scene_duration = 4.0
    groups: list[list[int]] = []
    current: list[int] = [0]
    for index in range(1, len(shots)):
        shot_duration = _shot_duration(shots[index])
        group_start = float(shots[current[0]].get("startSec", 0.0))
        group_end = float(shots[current[-1]].get("endSec", group_start))
        group_duration = group_end - group_start
        if shot_duration < merge_max and group_duration < max_scene_duration:
            current.append(index)
        else:
            groups.append(current)
            current = [index]
    groups.append(current)
    return groups


def _assign_merged_shot_ids(
    keyframes: list[dict[str, Any]],
    shots: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    groups = _merge_shot_groups(shots)
    shot_to_group: dict[int, str] = {}
    for group_index, group in enumerate(groups):
        scene_id = f"scene-{group_index}"
        for shot_index in group:
            shot_to_group[shot_index] = scene_id

    merged: list[dict[str, Any]] = []
    for frame in keyframes:
        shot_id = str(frame.get("shotId") or "")
        shot_index = _shot_index_from_id(shot_id)
        updated = dict(frame)
        if shot_index is not None and shot_index in shot_to_group:
            updated["shotId"] = shot_to_group[shot_index]
        merged.append(updated)
    return merged


def _boundary_shot_indices(shots: list[dict[str, Any]]) -> set[int]:
    indices: set[int] = set()
    for index, shot in enumerate(shots):
        if str(shot.get("changeReason") or "") != "histogram_cut":
            continue
        if float(shot.get("confidence") or 0.0) <= 0.8:
            continue
        indices.add(index)
    return indices


def _frames_for_shot_indices(
    keyframes: list[dict[str, Any]],
    shot_indices: set[int],
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for frame in keyframes:
        shot_index = _shot_index_from_id(str(frame.get("shotId") or ""))
        if shot_index is not None and shot_index in shot_indices:
            selected.append(frame)
    return selected


def _dedupe_by_path(frames: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen_paths: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for frame in frames:
        path = str(frame.get("path") or "")
        if path and path in seen_paths:
            continue
        if path:
            seen_paths.add(path)
        deduped.append(frame)
    return deduped


def _ensure_timeline_endpoints(
    selected: list[dict[str, Any]],
    keyframes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    paths = {str(frame.get("path") or "") for frame in selected}
    timeline_first = min(keyframes, key=lambda item: float(item.get("timeSec", 0.0)))
    timeline_last = max(keyframes, key=lambda item: float(item.get("timeSec", 0.0)))
    merged = list(selected)
    for frame in (timeline_first, timeline_last):
        path = str(frame.get("path") or "")
        if path and path in paths:
            continue
        merged.append(frame)
        if path:
            paths.add(path)
    return sorted(merged, key=lambda item: float(item.get("timeSec", 0.0)))


def select_keyframes_for_llm(
    keyframes: list[dict[str, Any]],
    shots: list[dict[str, Any]],
    *,
    duration_sec: float,
    analysis_depth: AnalysisDepth,
    max_per_video: int | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    if not keyframes:
        return [], warnings

    merged_frames = _assign_merged_shot_ids(keyframes, shots)
    best_per_scene = _pick_best_keyframes_per_shot(merged_frames)
    if not best_per_scene:
        return [], warnings

    cap = max_per_video if max_per_video is not None else default_max_keyframes_per_video(
        duration_sec,
        analysis_depth,
    )
    if len(best_per_scene) <= cap:
        selected = _ensure_timeline_endpoints(_dedupe_by_path(best_per_scene), keyframes)
        if len(selected) > cap:
            warnings.append(f"keyframe_sampling_applied:{len(best_per_scene)}->{cap}")
            selected = _apply_cap_preserving_endpoints(selected, keyframes, cap)
        return selected, warnings

    must_keep: list[dict[str, Any]] = []
    must_keep.append(min(keyframes, key=lambda item: float(item.get("timeSec", 0.0))))
    must_keep.append(max(keyframes, key=lambda item: float(item.get("timeSec", 0.0))))
    must_keep_paths = {str(frame.get("path") or "") for frame in must_keep if frame.get("path")}

    boundary_frames = _frames_for_shot_indices(keyframes, _boundary_shot_indices(shots))
    for frame in boundary_frames:
        path = str(frame.get("path") or "")
        if path and path in must_keep_paths:
            continue
        must_keep.append(frame)
        if path:
            must_keep_paths.add(path)

    remaining_cap = max(cap - len(must_keep), 0)
    pool = [
        frame
        for frame in best_per_scene
        if str(frame.get("path") or "") not in must_keep_paths
    ]
    sampled = _evenly_sample(pool, remaining_cap) if remaining_cap > 0 else []
    selected = sorted(
        must_keep + sampled,
        key=lambda item: float(item.get("timeSec", 0.0)),
    )
    deduped = _dedupe_by_path(selected)
    if len(deduped) > cap:
        deduped = _apply_cap_preserving_endpoints(deduped, keyframes, cap)

    warnings.append(f"keyframe_sampling_applied:{len(best_per_scene)}->{len(deduped)}")
    return _ensure_timeline_endpoints(deduped, keyframes), warnings


def _apply_cap_preserving_endpoints(
    frames: list[dict[str, Any]],
    keyframes: list[dict[str, Any]],
    cap: int,
) -> list[dict[str, Any]]:
    timeline_first = min(keyframes, key=lambda item: float(item.get("timeSec", 0.0)))
    timeline_last = max(keyframes, key=lambda item: float(item.get("timeSec", 0.0)))
    reserved = _dedupe_by_path([timeline_first, timeline_last])
    if cap <= len(reserved):
        return reserved[:cap]
    reserved_paths = {str(frame.get("path") or "") for frame in reserved}
    pool = [
        frame
        for frame in frames
        if str(frame.get("path") or "") not in reserved_paths
    ]
    sampled = _evenly_sample(pool, max(cap - len(reserved), 0))
    return sorted(reserved + sampled, key=lambda item: float(item.get("timeSec", 0.0)))
