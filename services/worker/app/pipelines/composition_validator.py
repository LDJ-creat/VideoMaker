from __future__ import annotations

from typing import Any


def validate_storyboard_timing_consistency(
    *,
    storyboard: list[dict[str, Any]],
    narration_duration_sec: float,
    tolerance_sec: float = 0.2,
) -> list[str]:
    """Return blocking error messages when scene windows disagree with canonical duration."""
    errors: list[str] = []
    if not storyboard:
        return errors
    last_end = 0.0
    for scene in storyboard:
        if not isinstance(scene, dict):
            continue
        start = float(scene.get("startSec", 0.0))
        end = float(scene.get("endSec", start))
        if end < start:
            errors.append(f"slot {scene.get('slotId')}: endSec before startSec")
        if start < last_end - 0.01:
            errors.append(f"slot {scene.get('slotId')}: overlaps previous scene")
        last_end = max(last_end, end)
    if narration_duration_sec > 0 and abs(last_end - narration_duration_sec) > tolerance_sec:
        errors.append(
            f"storyboard tail {last_end:.3f}s deviates from narration {narration_duration_sec:.3f}s"
        )
    return errors


def validate_material_spec_duration(
    *,
    spec: dict[str, Any],
    slot_timing: dict[str, float],
    tolerance_ratio: float = 0.05,
) -> list[str]:
    """Ensure material spec duration does not exceed authoritative slot window."""
    errors: list[str] = []
    spec_duration = float(spec.get("durationSec") or 0.0)
    allowed = float(slot_timing.get("durationSec") or 0.0)
    if allowed <= 0 or spec_duration <= 0:
        return errors
    if spec_duration > allowed * (1.0 + tolerance_ratio):
        errors.append(
            f"spec duration {spec_duration:.3f}s exceeds slot window {allowed:.3f}s"
        )
    return errors
