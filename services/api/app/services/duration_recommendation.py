from __future__ import annotations

import os
from typing import Any


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


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


def build_duration_recommendation(
    *,
    structure: dict[str, Any] | None,
    sample_id: str | None = None,
) -> dict[str, Any]:
    recommended = recommend_duration_from_structure(structure)
    return {
        "recommendedSec": recommended,
        "sampleId": sample_id,
        "structureDurationSec": recommended,
        "defaultTargetSec": recommended,
        "maxTargetSec": _env_float("VIDEOMAKER_DURATION_TARGET_MAX_SEC", 600.0),
    }
