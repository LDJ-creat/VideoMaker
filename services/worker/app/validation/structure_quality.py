from __future__ import annotations

import re
from typing import Any

_CRITICAL_PREFIX = "critical:"
_MIN_INTENT_LEN = 6
_ENGLISH_TOKEN_PATTERN = re.compile(r"[a-zA-Z]{4,}")


def _normalize_tokens(text: str) -> set[str]:
    tokens = re.findall(r"[\u4e00-\u9fff]+|[a-z0-9]+", text.lower())
    return {token for token in tokens if len(token) > 1}


def _overlap_ratio(left: str, right: str) -> float:
    left_tokens = _normalize_tokens(left)
    right_tokens = _normalize_tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0
    shared = left_tokens & right_tokens
    return len(shared) / min(len(left_tokens), len(right_tokens))


def _english_ratio(text: str) -> float:
    if not text.strip():
        return 0.0
    english = len(_ENGLISH_TOKEN_PATTERN.findall(text))
    chinese = len(re.findall(r"[\u4e00-\u9fff]", text))
    total = english + chinese
    if total == 0:
        return 0.0
    return english / total


def _l0_v3_satisfied(structure: dict[str, Any]) -> bool:
    verbal = structure.get("verbal") if isinstance(structure.get("verbal"), dict) else {}
    transfer = structure.get("transfer") if isinstance(structure.get("transfer"), dict) else {}
    context = structure.get("context") if isinstance(structure.get("context"), dict) else {}
    hook = str(verbal.get("hookTemplate", "")).strip()
    lever = str(transfer.get("differentiationLever", "")).strip()
    category = str(context.get("contentCategory", "")).strip()
    return len(hook) >= 4 and len(lever) >= 4 and len(category) >= 3


def evaluate_structure_quality(structure: dict[str, Any]) -> dict[str, Any]:
    warnings: list[str] = []
    narrative = structure.get("narrative") if isinstance(structure.get("narrative"), dict) else {}
    segments = list(narrative.get("segments") or [])
    slots = list(structure.get("slots") or [])
    version = str(structure.get("version") or "")
    rhythm = structure.get("rhythm") if isinstance(structure.get("rhythm"), dict) else {}

    slot_roles = [str(slot.get("role", "")) for slot in slots if isinstance(slot, dict)]
    if slot_roles and len(set(slot_roles)) == 1:
        warnings.append(f"{_CRITICAL_PREFIX} slot_roles_uniform:{slot_roles[0]}")

    for slot in slots:
        if not isinstance(slot, dict):
            continue
        visual_intent = str(slot.get("visualIntent", "")).strip()
        script_intent = str(slot.get("scriptIntent", "")).strip()
        if visual_intent and script_intent and visual_intent == script_intent:
            warnings.append(f"slot_intent_duplicate:{slot.get('id', 'unknown')}")

    beat_points = [
        float(value)
        for value in (rhythm.get("beatPoints") or [])
        if isinstance(value, (int, float))
    ]
    shot_starts = [
        float(item.get("startSec", 0.0))
        for item in (rhythm.get("shotBoundaries") or [])
        if isinstance(item, dict)
    ]
    if beat_points and shot_starts and len(beat_points) >= 3:
        tolerance = 0.35
        matched = sum(
            1
            for beat in beat_points
            if any(abs(beat - start) <= tolerance for start in shot_starts)
        )
        if matched / len(beat_points) >= 0.85:
            warnings.append("beat_points_mirror_shots")

    for segment in segments:
        if not isinstance(segment, dict):
            continue
        intent = str(segment.get("intent", ""))
        if len(intent.strip()) < _MIN_INTENT_LEN:
            warnings.append(f"segment_intent_short:{segment.get('id', 'unknown')}")
        visual = str(segment.get("visualSummary", ""))
        script = str(segment.get("scriptSummary", ""))
        if _overlap_ratio(visual, script) > 0.85:
            warnings.append(f"segment_summary_duplicate:{segment.get('id', 'unknown')}")

    if version == "p1-v3":
        for segment in segments:
            if not isinstance(segment, dict):
                continue
            if not str(segment.get("transcriptExcerpt", "")).strip():
                warnings.append(f"{_CRITICAL_PREFIX} missing_transcript_excerpt:{segment.get('id')}")
        if not _l0_v3_satisfied(structure):
            warnings.append(f"{_CRITICAL_PREFIX} v3_l0_incomplete")
        verbal = structure.get("verbal") if isinstance(structure.get("verbal"), dict) else {}
        transfer = structure.get("transfer") if isinstance(structure.get("transfer"), dict) else {}
        if not str(verbal.get("ctaMechanism", "")).strip():
            warnings.append("missing_cta_mechanism")
        if not list(transfer.get("emotionTriggers") or []):
            warnings.append("missing_emotion_triggers")

    summary = str(narrative.get("summary", ""))
    joined_segments = " ".join(
        f"{segment.get('visualSummary', '')} {segment.get('scriptSummary', '')}"
        for segment in segments
        if isinstance(segment, dict)
    )
    if joined_segments and _overlap_ratio(summary, joined_segments) > 0.75:
        warnings.append("narrative_summary_repeats_segments")

    locale = str((structure.get("analysisQuality") or {}).get("locale") or "zh")
    if locale.startswith("zh"):
        english_ratio = _english_ratio(summary)
        if english_ratio > 0.35:
            warnings.append(f"{_CRITICAL_PREFIX} locale_not_chinese:summary_english_ratio={english_ratio:.2f}")

    promote_ready = not has_critical_warnings(warnings)
    if version == "p1-v3":
        promote_ready = promote_ready and _l0_v3_satisfied(structure)

    return {"warnings": warnings, "promoteReady": promote_ready}


def has_critical_warnings(warnings: list[str]) -> bool:
    return any(str(item).startswith(_CRITICAL_PREFIX) for item in warnings)
