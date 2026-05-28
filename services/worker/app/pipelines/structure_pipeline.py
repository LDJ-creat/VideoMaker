from __future__ import annotations

from collections import Counter
import math
from statistics import mean, pstdev
from typing import Any

from app.validation.schema_loader import validate_contract


PROBLEM_KEYWORDS = {
    "pain",
    "difficult",
    "tired",
    "expensive",
    "slow",
    "trouble",
    "痛点",
    "困扰",
    "麻烦",
    "太贵",
}
BENEFIT_KEYWORDS = {
    "save",
    "faster",
    "better",
    "improve",
    "easy",
    "省",
    "快",
    "提升",
    "方便",
}
PROOF_KEYWORDS = {
    "real",
    "test",
    "result",
    "compare",
    "before",
    "after",
    "真实",
    "实测",
    "对比",
    "效果",
}
CTA_KEYWORDS = {
    "buy",
    "click",
    "order",
    "follow",
    "learn more",
    "下单",
    "点击",
    "关注",
    "购买",
}

SEGMENT_SLOT_RULES: dict[str, list[str]] = {
    "hook": ["hook_visual", "hook_text"],
    "benefit": ["benefit_card"],
    "solution": ["usage_scene"],
    "proof": ["proof"],
    "comparison": ["comparison"],
    "cta": ["cta"],
    "problem": ["comparison"],
}

SLOT_REQUIRED_TYPES: dict[str, list[str]] = {
    "hook_visual": ["video", "image"],
    "hook_text": ["text", "packaging"],
    "benefit_card": ["text", "packaging"],
    "usage_scene": ["video", "image"],
    "proof": ["video", "image", "text"],
    "comparison": ["video", "image", "text", "packaging"],
    "cta": ["text", "packaging"],
}

SLOT_IMPORTANCE: dict[str, str] = {
    "hook_visual": "must_have",
    "hook_text": "recommended",
    "benefit_card": "recommended",
    "usage_scene": "must_have",
    "proof": "recommended",
    "comparison": "recommended",
    "cta": "must_have",
}


def _normalize_transcript_segments(transcript: Any) -> list[dict[str, Any]]:
    """Accept whisper-style `{segments: [...]}` or a flat segment list."""
    if isinstance(transcript, dict):
        segments = transcript.get("segments", [])
    elif isinstance(transcript, list):
        segments = transcript
    else:
        return []

    if not isinstance(segments, list):
        return []
    return [item for item in segments if isinstance(item, dict)]


def extract_video_structure(
    *,
    sample_analysis: dict[str, Any],
    project_id: str,
    source_video_id: str,
    version: str = "p0-v1",
) -> dict[str, Any]:
    metadata = sample_analysis.get("metadata", {})
    transcript = _normalize_transcript_segments(sample_analysis.get("transcript", []))
    shots = sample_analysis.get("shots", [])
    keyframes = sample_analysis.get("keyframes", [])
    duration = float(metadata.get("durationSec") or _duration_from_shots(shots) or 0.0)

    rhythm = _build_rhythm_profile(duration=duration, shots=shots)
    segments = _build_segments(duration=duration, transcript=transcript)
    slots = _build_slots(segments=segments)
    evidence = _build_evidence(
        segments=segments, slots=slots, transcript=transcript, shots=shots, keyframes=keyframes
    )
    packaging = {
        "titleCards": [],
        "stickers": [],
        "transitions": [],
        "visualDensity": _visual_density(duration=duration, transcript=transcript),
    }

    structure = {
        "id": f"video-structure-{project_id}",
        "projectId": project_id,
        "sourceVideoId": source_video_id,
        "version": version,
        "metadata": {
            "durationSec": duration,
            "width": metadata.get("width"),
            "height": metadata.get("height"),
            "fps": metadata.get("fps"),
            "hasAudio": metadata.get("hasAudio"),
        },
        "narrative": {
            "summary": "Deterministic structure extraction result",
            "segments": segments,
        },
        "rhythm": rhythm,
        "packaging": packaging,
        "slots": slots,
        "evidence": evidence,
        "confidence": 0.82,
    }
    structure["metadata"] = {
        key: value for key, value in structure["metadata"].items() if value is not None
    }

    validation = validate_contract("video-structure", structure)
    if not validation.valid:
        raise ValueError(f"Invalid VideoStructure payload: {validation.errors}")
    return structure


def _duration_from_shots(shots: list[dict[str, Any]]) -> float:
    if not shots:
        return 0.0
    return max(float(shot.get("endSec", 0.0)) for shot in shots)


def _build_rhythm_profile(*, duration: float, shots: list[dict[str, Any]]) -> dict[str, Any]:
    shot_boundaries: list[dict[str, Any]] = []
    shot_durations: list[float] = []
    beat_points: list[float] = []

    for shot in shots:
        start = float(shot.get("startSec", 0.0))
        end = float(shot.get("endSec", start))
        conf = float(shot.get("confidence", 0.0))
        reason = str(shot.get("changeReason", "unknown"))
        shot_boundaries.append(
            {
                "startSec": max(0.0, start),
                "endSec": max(start, end),
                "confidence": min(1.0, max(0.0, conf)),
                "changeReason": reason
                if reason in {"visual_cut", "scene_change", "caption_change", "beat", "unknown"}
                else "unknown",
            }
        )
        shot_durations.append(max(0.0, end - start))
        beat_points.append(max(0.0, start))

    avg_duration = mean(shot_durations) if shot_durations else 0.0
    tempo = _classify_tempo(avg_duration=avg_duration, shot_durations=shot_durations)

    return {
        "totalDurationSec": duration,
        "shotCount": len(shots),
        "avgShotDurationSec": avg_duration,
        "tempo": tempo,
        "beatPoints": sorted(set(round(point, 3) for point in beat_points)),
        "shotBoundaries": shot_boundaries,
    }


def _classify_tempo(*, avg_duration: float, shot_durations: list[float]) -> str:
    if not shot_durations:
        return "slow"

    if len(shot_durations) > 1 and avg_duration > 0:
        cv = pstdev(shot_durations) / avg_duration
        if cv > 0.65:
            return "mixed"

    if avg_duration < 1.2:
        return "fast"
    if avg_duration > 2.8:
        return "slow"
    return "medium"


def _build_segments(*, duration: float, transcript: list[dict[str, Any]]) -> list[dict[str, Any]]:
    hook_end = min(3.0, duration * 0.15)
    second_end = min(duration, hook_end + duration * 0.25)
    middle_end = min(duration, second_end + duration * 0.40)
    cta_start = max(duration - max(2.0, duration * 0.15), middle_end)

    second_role = _select_role(
        transcript=_transcript_slice(transcript, hook_end, second_end),
        positive="benefit",
        positive_keywords=BENEFIT_KEYWORDS,
        negative="problem",
        negative_keywords=PROBLEM_KEYWORDS,
    )
    third_role = _select_role(
        transcript=_transcript_slice(transcript, second_end, middle_end),
        positive="proof",
        positive_keywords=PROOF_KEYWORDS,
        negative="solution",
        negative_keywords=BENEFIT_KEYWORDS,
    )

    segments = [
        _segment("seg-hook", "hook", 0.0, hook_end, transcript),
        _segment("seg-2", second_role, hook_end, second_end, transcript),
        _segment("seg-3", third_role, second_end, middle_end, transcript),
        _segment("seg-cta", "cta", cta_start, duration, transcript),
    ]

    if _contains_keyword(_transcript_text(transcript), CTA_KEYWORDS):
        segments[-1]["role"] = "cta"
    return segments


def _segment(
    segment_id: str,
    role: str,
    start_sec: float,
    end_sec: float,
    transcript: list[dict[str, Any]],
) -> dict[str, Any]:
    snippet = _transcript_slice(transcript, start_sec, end_sec)
    script_summary = _transcript_text(snippet)[:120] or f"{role} narrative"
    visual_summary = f"{role} visual flow"
    return {
        "id": segment_id,
        "role": role,
        "startSec": round(max(0.0, start_sec), 3),
        "endSec": round(max(start_sec, end_sec), 3),
        "scriptSummary": script_summary,
        "visualSummary": visual_summary,
        "intent": role,
    }


def _build_slots(*, segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    slots: list[dict[str, Any]] = []
    for segment in segments:
        segment_slots = SEGMENT_SLOT_RULES.get(segment["role"], [])
        concise_intent = _compress_intent(segment["scriptSummary"], segment["role"])
        for index, role in enumerate(segment_slots):
            slot_id = f"{segment['id']}-{role}-{index + 1}"
            slots.append(
                {
                    "id": slot_id,
                    "segmentId": segment["id"],
                    "role": role,
                    "startSec": segment["startSec"],
                    "endSec": segment["endSec"],
                    "requiredAssetType": SLOT_REQUIRED_TYPES.get(role, ["text"]),
                    "visualIntent": concise_intent,
                    "scriptIntent": concise_intent,
                    "packagingHint": "highlight key message"
                    if role in {"hook_text", "benefit_card", "comparison", "cta"}
                    else None,
                    "importance": SLOT_IMPORTANCE.get(role, "optional"),
                    "constraints": [],
                }
            )
    for slot in slots:
        if slot["packagingHint"] is None:
            del slot["packagingHint"]
    return slots


def _compress_intent(script_summary: str, role: str) -> str:
    keywords = [
        "真实",
        "使用",
        "效率",
        "提升",
        "产品",
        "场景",
        "对比",
        "购买",
        "点击",
        "方便",
        "快",
    ]
    picked = [keyword for keyword in keywords if keyword in script_summary]
    if picked:
        return f"{role} " + " ".join(picked[:4])
    return f"{role} {script_summary[:40]}"


def _build_evidence(
    *,
    segments: list[dict[str, Any]],
    slots: list[dict[str, Any]],
    transcript: list[dict[str, Any]],
    shots: list[dict[str, Any]],
    keyframes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for segment in segments:
        segment_text = _transcript_text(
            _transcript_slice(transcript, segment["startSec"], segment["endSec"])
        )
        evidence.append(
            {
                "targetId": segment["id"],
                "source": "asr",
                "summary": segment_text[:120] or "no transcript overlap",
                "confidence": 0.8 if segment_text else 0.5,
            }
        )

        overlap_shots = [
            shot
            for shot in shots
            if float(shot.get("startSec", 0.0)) < segment["endSec"]
            and float(shot.get("endSec", 0.0)) > segment["startSec"]
        ]
        if overlap_shots:
            evidence.append(
                {
                    "targetId": segment["id"],
                    "source": "shot_detection",
                    "summary": f"{len(overlap_shots)} overlapping shot boundaries",
                    "confidence": 0.75,
                }
            )

    for slot in slots:
        slot_keyframes = [
            frame
            for frame in keyframes
            if slot["startSec"] <= float(frame.get("timeSec", 0.0)) <= slot["endSec"]
        ]
        if slot_keyframes:
            summary = ",".join(str(frame.get("path", "")) for frame in slot_keyframes[:3])
            evidence.append(
                {
                    "targetId": slot["id"],
                    "source": "keyframe",
                    "summary": summary or "keyframes linked",
                    "confidence": 0.78,
                }
            )
    return evidence


def _visual_density(*, duration: float, transcript: list[dict[str, Any]]) -> str:
    if duration <= 0:
        return "low"
    text = _transcript_text(transcript)
    chars_per_sec = len(text) / duration
    if chars_per_sec > 8:
        return "high"
    if chars_per_sec > 3:
        return "medium"
    return "low"


def _transcript_slice(
    transcript: list[dict[str, Any]], start_sec: float, end_sec: float
) -> list[dict[str, Any]]:
    return [
        item
        for item in transcript
        if float(item.get("startSec", 0.0)) < end_sec and float(item.get("endSec", 0.0)) > start_sec
    ]


def _transcript_text(transcript: list[dict[str, Any]]) -> str:
    return " ".join(str(item.get("text", "")) for item in transcript).strip()


def _contains_keyword(text: str, keywords: set[str]) -> bool:
    lowered = text.lower()
    return any(keyword.lower() in lowered for keyword in keywords)


def _select_role(
    *,
    transcript: list[dict[str, Any]],
    positive: str,
    positive_keywords: set[str],
    negative: str,
    negative_keywords: set[str],
) -> str:
    text = _transcript_text(transcript).lower()
    tokens = _tokenize(text)
    token_counter = Counter(tokens)
    positive_score = sum(token_counter[keyword.lower()] for keyword in positive_keywords)
    negative_score = sum(token_counter[keyword.lower()] for keyword in negative_keywords)
    return positive if positive_score >= negative_score else negative


def _tokenize(text: str) -> list[str]:
    normalized = "".join(ch if ch.isalnum() else " " for ch in text)
    tokens = [token for token in normalized.split() if token]
    # Also keep common CJK keywords by direct include check.
    cjk_tokens = []
    for keyword in PROBLEM_KEYWORDS | BENEFIT_KEYWORDS | PROOF_KEYWORDS | CTA_KEYWORDS:
        if keyword in text:
            cjk_tokens.append(keyword.lower())
    return tokens + cjk_tokens

