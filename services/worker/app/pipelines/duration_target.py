from __future__ import annotations

import copy
import os
from typing import Any


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def duration_target_max_sec() -> float:
    return _env_float("VIDEOMAKER_DURATION_TARGET_MAX_SEC", 600.0)


def short_form_max_sec() -> float:
    return _env_float("VIDEOMAKER_SHORT_FORM_MAX_SEC", 60.0)


def recommend_duration_from_structure(structure: dict[str, Any] | None) -> float:
    if not isinstance(structure, dict):
        return 30.0
    metadata = structure.get("metadata")
    if isinstance(metadata, dict):
        duration = metadata.get("durationSec")
        if duration is not None:
            value = float(duration)
            if value > 0:
                return round(value, 2)
    slots = structure.get("slots")
    if isinstance(slots, list) and slots:
        end_values = [
            float(slot.get("endSec", 0.0))
            for slot in slots
            if isinstance(slot, dict)
        ]
        if end_values:
            return round(max(end_values), 2)
    return 30.0


def _clamp_target(value: float) -> float:
    maximum = duration_target_max_sec()
    return max(1.0, min(value, maximum))


def normalize_duration_target(
    brief: dict[str, Any] | None,
    structure: dict[str, Any] | None,
) -> dict[str, Any]:
    recommended = recommend_duration_from_structure(structure)
    raw = dict((brief or {}).get("durationTarget") or {})
    source = str(raw.get("source") or "default")
    target = raw.get("targetSec")
    if target is None:
        target = recommended
        if not raw:
            source = "sample" if structure else "default"
    target_sec = _clamp_target(float(target))
    normalized: dict[str, Any] = {
        "targetSec": round(target_sec, 2),
        "recommendedSec": round(recommended, 2),
        "source": source if source in {"sample", "user", "default"} else "user",
    }
    min_sec = raw.get("minSec")
    max_sec = raw.get("maxSec")
    if min_sec is not None:
        normalized["minSec"] = _clamp_target(float(min_sec))
    if max_sec is not None:
        normalized["maxSec"] = _clamp_target(float(max_sec))
    if "minSec" in normalized and target_sec < normalized["minSec"]:
        normalized["targetSec"] = normalized["minSec"]
    if "maxSec" in normalized and target_sec > normalized["maxSec"]:
        normalized["targetSec"] = normalized["maxSec"]
    return normalized


def _scale_time_fields(payload: dict[str, Any], ratio: float) -> None:
    for key in ("startSec", "endSec"):
        if key in payload and payload[key] is not None:
            payload[key] = round(float(payload[key]) * ratio, 3)


def scale_structure_to_target_duration(
    structure: dict[str, Any],
    target_sec: float,
) -> dict[str, Any]:
    scaled = copy.deepcopy(structure)
    source_duration = recommend_duration_from_structure(structure)
    if source_duration <= 0:
        source_duration = max(target_sec, 1.0)
    ratio = float(target_sec) / source_duration

    metadata = scaled.get("metadata")
    if isinstance(metadata, dict):
        metadata["durationSec"] = round(float(target_sec), 3)

    narrative = scaled.get("narrative")
    if isinstance(narrative, dict):
        segments = narrative.get("segments")
        if isinstance(segments, list):
            for segment in segments:
                if isinstance(segment, dict):
                    _scale_time_fields(segment, ratio)

    slots = scaled.get("slots")
    if isinstance(slots, list):
        for slot in slots:
            if isinstance(slot, dict):
                _scale_time_fields(slot, ratio)

    rhythm = scaled.get("rhythm")
    if isinstance(rhythm, dict):
        beat_points = rhythm.get("beatPoints")
        if isinstance(beat_points, list):
            for beat in beat_points:
                if isinstance(beat, dict) and beat.get("timeSec") is not None:
                    beat["timeSec"] = round(float(beat["timeSec"]) * ratio, 3)

    return scaled
