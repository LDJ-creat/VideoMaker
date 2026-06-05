from __future__ import annotations

import re
from typing import Any

_CRITICAL_PREFIX = "critical:"
_MIN_INTENT_LEN = 6
_MIN_MIGRATION_LEN = 8
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


def evaluate_structure_quality(structure: dict[str, Any]) -> dict[str, Any]:
    warnings: list[str] = []
    narrative = structure.get("narrative") if isinstance(structure.get("narrative"), dict) else {}
    segments = list(narrative.get("segments") or [])
    slots = list(structure.get("slots") or [])
    version = str(structure.get("version") or "")

    slot_roles = [str(slot.get("role", "")) for slot in slots if isinstance(slot, dict)]
    if slot_roles and len(set(slot_roles)) == 1:
        warnings.append(f"{_CRITICAL_PREFIX} slot_roles_uniform:{slot_roles[0]}")

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

    if version == "p1-v2":
        for segment in segments:
            if not isinstance(segment, dict):
                continue
            if not str(segment.get("transcriptExcerpt", "")).strip():
                warnings.append(f"{_CRITICAL_PREFIX} missing_transcript_excerpt:{segment.get('id')}")
        for slot in slots:
            if not isinstance(slot, dict):
                continue
            migration = str(slot.get("migrationTemplate", "")).strip()
            if len(migration) < _MIN_MIGRATION_LEN:
                warnings.append(f"missing_migration_template:{slot.get('id')}")

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

    return {"warnings": warnings}


def has_critical_warnings(warnings: list[str]) -> bool:
    return any(str(item).startswith(_CRITICAL_PREFIX) for item in warnings)
