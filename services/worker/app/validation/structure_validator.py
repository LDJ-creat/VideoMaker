from __future__ import annotations

import re
from typing import Any

_SEGMENT_EVIDENCE_SOURCES = frozenset({"asr", "shot_detection", "keyframe", "ocr", "audio"})
_CTA_END_TOLERANCE = 0.15
_RHYTHM_TOLERANCE_SEC = 0.5
_ASR_TIME_PATTERN = re.compile(
    r"\d+(\.\d+)?\s*-\s*\d+(\.\d+)?\s*(?:s|sec)\b",
    re.IGNORECASE,
)
_KEYFRAME_PATH_PATTERN = re.compile(r"keyframes/[\w./-]+\.(?:jpg|jpeg|png|webp)", re.IGNORECASE)
_SHOT_BOUNDARY_PATTERN = re.compile(r"\d+(\.\d+)?")


class StructureValidationError(ValueError):
    """Raised when VideoStructure fails post-schema semantic checks."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        message = "; ".join(errors)
        super().__init__(message)


def _evidence_summary_valid(source: str, summary: str) -> bool:
    text = summary.strip()
    if not text:
        return False
    if source == "asr":
        return bool(_ASR_TIME_PATTERN.search(text))
    if source == "keyframe":
        return bool(_KEYFRAME_PATH_PATTERN.search(text))
    if source == "shot_detection":
        return bool(_SHOT_BOUNDARY_PATTERN.search(text))
    return True


def _validate_rhythm_alignment(
    structure: dict[str, Any],
    reference_shots: list[dict[str, Any]],
    errors: list[str],
) -> None:
    boundaries = structure.get("rhythm", {}).get("shotBoundaries", [])
    if len(boundaries) != len(reference_shots):
        errors.append(
            "rhythm.shotBoundaries length must match analysis shots "
            f"({len(boundaries)} vs {len(reference_shots)})"
        )
        return
    for index, (shot, boundary) in enumerate(zip(reference_shots, boundaries, strict=True)):
        start_delta = abs(float(shot["startSec"]) - float(boundary["startSec"]))
        end_delta = abs(float(shot["endSec"]) - float(boundary["endSec"]))
        if start_delta > _RHYTHM_TOLERANCE_SEC or end_delta > _RHYTHM_TOLERANCE_SEC:
            errors.append(
                "rhythm.shotBoundaries must align with analysis shots within "
                f"{_RHYTHM_TOLERANCE_SEC}s (shot index {index})"
            )


def validate_video_structure(
    structure: dict[str, Any],
    *,
    reference_shots: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    errors: list[str] = []

    confidence = structure.get("confidence")
    if not isinstance(confidence, (int, float)) or confidence < 0 or confidence > 1:
        errors.append("confidence must be between 0 and 1")

    segments = structure.get("narrative", {}).get("segments", [])
    segment_ids = {segment["id"] for segment in segments if segment.get("id")}
    evidence_items = list(structure.get("evidence", []))
    evidence_by_target: dict[str, list[dict[str, Any]]] = {}
    for item in evidence_items:
        target_id = item.get("targetId")
        if not target_id:
            continue
        evidence_by_target.setdefault(str(target_id), []).append(item)

    for segment_id in segment_ids:
        matches = evidence_by_target.get(segment_id, [])
        valid = [
            item
            for item in matches
            if item.get("source") in _SEGMENT_EVIDENCE_SOURCES
            and _evidence_summary_valid(str(item.get("source", "")), str(item.get("summary", "")))
        ]
        if not valid:
            errors.append(f"segment evidence required for '{segment_id}'")

    for slot in structure.get("slots", []):
        segment_id = slot.get("segmentId")
        if segment_id not in segment_ids:
            errors.append(f"slot segmentId '{segment_id}' is not a narrative segment")

    duration_sec = float(structure.get("metadata", {}).get("durationSec", 0))
    if duration_sec > 0:
        min_cta_end = duration_sec * (1 - _CTA_END_TOLERANCE)
        for segment in segments:
            if segment.get("role") == "cta" and float(segment.get("endSec", 0)) < min_cta_end:
                errors.append("cta segment must end within the final 15% of video duration")

    if reference_shots:
        _validate_rhythm_alignment(structure, reference_shots, errors)

    if errors:
        raise StructureValidationError(errors)
    return structure
