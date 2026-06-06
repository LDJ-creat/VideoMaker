from __future__ import annotations

import re
from typing import Any

_SEGMENT_EVIDENCE_SOURCES = frozenset({"asr", "shot_detection", "keyframe", "ocr", "audio"})
_CTA_END_TOLERANCE = 0.15
_RHYTHM_TOLERANCE_SEC = 0.5
_BEAT_ONSET_TOLERANCE_SEC = 0.3
_MIN_TRANSCRIPT_EXCERPT_LEN = 4
_MIN_SUMMARY_FIELD_LEN = 10
_MAX_OVERLAP_RATIO = 0.85
_ASR_TIME_PATTERN = re.compile(
    r"\d+(\.\d+)?\s*-\s*\d+(\.\d+)?\s*(?:s|sec)\b",
    re.IGNORECASE,
)
_KEYFRAME_PATH_PATTERN = re.compile(r"keyframes/[\w./-]+\.(?:jpg|jpeg|png|webp)", re.IGNORECASE)
_KEYFRAME_TIMESTAMP_PATTERN = re.compile(
    r"\d+(?:\.\d+)?\s*(?:s|sec|秒)\b"
    r"|"
    r"\d+(?:\.\d+)?\s*-\s*\d+(?:\.\d+)?\s*(?:s|sec|秒)?",
    re.IGNORECASE,
)
_SHOT_BOUNDARY_PATTERN = re.compile(r"\d+(\.\d+)?")
_AUDIO_TIME_PATTERN = re.compile(
    r"\d+(\.\d+)?\s*-\s*\d+(\.\d+)?",
    re.IGNORECASE,
)
_TEMPLATE_BLACKLIST = (
    "engaging opening",
    "captures viewer",
    "clear call-to-action",
    "call to action urging",
    "briefly presents the product",
    "highlights a common issue",
    "hook visual flow",
    "benefit visual flow",
    "proof visual flow",
    "cta visual flow",
)


class StructureValidationError(ValueError):
    """Raised when VideoStructure fails post-schema semantic checks."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        message = "; ".join(errors)
        super().__init__(message)


def _normalize_tokens(text: str) -> set[str]:
    lowered = text.lower()
    tokens = re.findall(r"[\u4e00-\u9fff]+|[a-z0-9]+", lowered)
    return {token for token in tokens if len(token) > 1}


def _overlap_ratio(left: str, right: str) -> float:
    left_tokens = _normalize_tokens(left)
    right_tokens = _normalize_tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0
    shared = left_tokens & right_tokens
    return len(shared) / min(len(left_tokens), len(right_tokens))


def _contains_blacklist(text: str) -> bool:
    lowered = text.lower()
    return any(phrase in lowered for phrase in _TEMPLATE_BLACKLIST)


def _field_too_short(text: str) -> bool:
    return len(text.strip()) < _MIN_SUMMARY_FIELD_LEN


def _evidence_summary_valid(
    source: str,
    summary: str,
    *,
    excerpt: str = "",
    time_range: dict[str, Any] | None = None,
) -> bool:
    text = summary.strip()
    if not text:
        return False
    if source == "asr":
        has_time = bool(_ASR_TIME_PATTERN.search(text))
        has_excerpt = len(excerpt.strip()) >= 4
        return has_time or has_excerpt
    if source == "keyframe":
        if _KEYFRAME_PATH_PATTERN.search(text):
            return True
        if _KEYFRAME_TIMESTAMP_PATTERN.search(text):
            return True
        if isinstance(time_range, dict):
            start = time_range.get("startSec")
            end = time_range.get("endSec")
            if isinstance(start, (int, float)) and isinstance(end, (int, float)) and float(end) >= float(start):
                return True
        return False
    if source == "shot_detection":
        return bool(_SHOT_BOUNDARY_PATTERN.search(text))
    if source == "audio":
        return bool(_AUDIO_TIME_PATTERN.search(text))
    if source == "ocr":
        return len(text.strip()) >= 2 or len(excerpt.strip()) >= 2
    return True


def _validate_anti_template(structure: dict[str, Any], errors: list[str]) -> None:
    for segment in structure.get("narrative", {}).get("segments", []):
        segment_id = str(segment.get("id", ""))
        visual = str(segment.get("visualSummary", ""))
        script = str(segment.get("scriptSummary", ""))
        for label, value in (("visualSummary", visual), ("scriptSummary", script)):
            if _field_too_short(value):
                errors.append(f"segment '{segment_id}' {label} too short or generic")
            if _contains_blacklist(value):
                errors.append(f"segment '{segment_id}' {label} matches template blacklist")

        if visual.strip() and script.strip():
            if _overlap_ratio(visual, script) >= _MAX_OVERLAP_RATIO:
                errors.append(
                    f"segment '{segment_id}' visualSummary and scriptSummary are too similar"
                )

    for slot in structure.get("slots", []):
        slot_id = str(slot.get("id", ""))
        visual_intent = str(slot.get("visualIntent", ""))
        script_intent = str(slot.get("scriptIntent", ""))
        for label, value in (("visualIntent", visual_intent), ("scriptIntent", script_intent)):
            if _field_too_short(value):
                errors.append(f"slot '{slot_id}' {label} too short or generic")
            if _contains_blacklist(value):
                errors.append(f"slot '{slot_id}' {label} matches template blacklist")


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


def _validate_v2_depth(
    structure: dict[str, Any],
    errors: list[str],
) -> None:
    version = str(structure.get("version") or "")
    if version != "p1-v2":
        return
    for segment in structure.get("narrative", {}).get("segments", []):
        if not isinstance(segment, dict):
            continue
        segment_id = str(segment.get("id", ""))
        excerpt = str(segment.get("transcriptExcerpt", "")).strip()
        if len(excerpt) < _MIN_TRANSCRIPT_EXCERPT_LEN:
            errors.append(f"v2 segment '{segment_id}' missing transcriptExcerpt")


def _validate_audio_profile_alignment(
    structure: dict[str, Any],
    analysis: dict[str, Any] | None,
    evidence_by_target: dict[str, list[dict[str, Any]]],
    segment_ids: set[str],
    errors: list[str],
) -> None:
    if not analysis:
        return
    audio_profile = analysis.get("audioProfile")
    if not isinstance(audio_profile, dict):
        return

    if audio_profile.get("hasVoiceover"):
        for segment_id in segment_ids:
            matches = evidence_by_target.get(segment_id, [])
            has_audio = any(item.get("source") == "audio" for item in matches)
            has_asr = any(item.get("source") == "asr" for item in matches)
            if not has_audio and not has_asr:
                errors.append(
                    f"segment '{segment_id}' requires audio or asr evidence when voiceover is present"
                )

    onset_times = [
        float(value)
        for value in (audio_profile.get("onsetTimes") or [])
        if isinstance(value, (int, float))
    ]
    if not onset_times:
        return
    beat_points = [
        float(value)
        for value in structure.get("rhythm", {}).get("beatPoints", [])
        if isinstance(value, (int, float))
    ]
    if len(beat_points) < 2:
        return
    unmatched = 0
    for beat in beat_points:
        if not any(abs(beat - onset) <= _BEAT_ONSET_TOLERANCE_SEC for onset in onset_times):
            unmatched += 1
    if unmatched > max(1, len(beat_points) // 2):
        errors.append(
            "rhythm.beatPoints not aligned with audioProfile.onsetTimes "
            f"(±{_BEAT_ONSET_TOLERANCE_SEC}s)"
        )


def validate_video_structure(
    structure: dict[str, Any],
    *,
    reference_shots: list[dict[str, Any]] | None = None,
    analysis: dict[str, Any] | None = None,
    anti_template: bool = True,
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
            and _evidence_summary_valid(
                str(item.get("source", "")),
                str(item.get("summary", "")),
                excerpt=str(item.get("excerpt", "")),
                time_range=item.get("timeRange") if isinstance(item.get("timeRange"), dict) else None,
            )
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

    _validate_v2_depth(structure, errors)
    _validate_audio_profile_alignment(
        structure,
        analysis,
        evidence_by_target,
        segment_ids,
        errors,
    )

    if anti_template:
        _validate_anti_template(structure, errors)

    if errors:
        raise StructureValidationError(errors)
    return structure
