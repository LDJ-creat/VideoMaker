from __future__ import annotations

import re
from typing import Any

_ALLOWED_METADATA_KEYS = frozenset(
    {"durationSec", "width", "height", "fps", "codec", "hasAudio"}
)
_ASR_RANGE_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*(?:to|-)\s*(\d+(?:\.\d+)?)")
_SHOT_BOUNDARY_PATTERN = re.compile(r"\d+(?:\.\d+)?")
_SLOT_ROLE_ALIASES = {
    "attention_grabber": "hook_visual",
    "intro": "hook_visual",
    "pain_point": "usage_scene",
    "problem_visual": "usage_scene",
    "problem": "usage_scene",
    "product_intro": "product_closeup",
    "solution": "product_closeup",
    "benefit": "benefit_card",
    "call_to_action": "cta",
    "cta_visual": "cta",
    "hook": "hook_visual",
    "proof": "proof",
    "comparison": "comparison",
    "transition": "transition",
}
_DEFAULT_PACKAGING = {
    "titleCards": [],
    "stickers": [],
    "transitions": [],
    "visualDensity": "medium",
}


def _compute_rhythm_facts(
    shots: list[dict[str, Any]],
    *,
    duration_sec: float | None = None,
) -> dict[str, Any]:
    if not shots:
        return {
            "shotCount": 0,
            "avgShotDurationSec": 0.0,
            "tempoHint": "slow",
            "durationSec": duration_sec or 0.0,
        }

    durations = [float(shot["endSec"]) - float(shot["startSec"]) for shot in shots]
    avg = sum(durations) / len(durations)
    if len(durations) > 1 and avg > 0:
        variance = sum((value - avg) ** 2 for value in durations) / len(durations)
        cv = (variance**0.5) / avg
    else:
        cv = 0.0

    if cv > 0.65:
        tempo_hint = "mixed"
    elif avg < 1.2:
        tempo_hint = "fast"
    elif avg <= 2.8:
        tempo_hint = "medium"
    else:
        tempo_hint = "slow"

    return {
        "shotCount": len(shots),
        "avgShotDurationSec": round(avg, 3),
        "tempoHint": tempo_hint,
        "durationSec": duration_sec if duration_sec is not None else shots[-1]["endSec"],
    }


def _normalize_evidence_summary(
    *,
    source: str,
    summary: str,
    segment: dict[str, Any],
) -> str:
    if source == "asr":
        match = _ASR_RANGE_PATTERN.search(summary)
        if match:
            return f"{match.group(1)}-{match.group(2)} sec"
        return f"{segment.get('startSec', 0.0)}-{segment.get('endSec', 0.0)} sec"
    if source == "shot_detection":
        if _SHOT_BOUNDARY_PATTERN.search(summary):
            return summary
        return f"{segment.get('startSec', 0.0)}-{segment.get('endSec', 0.0)} sec"
    return summary


def _ensure_segment_evidence(
    evidence: list[dict[str, Any]],
    *,
    segments: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    segments_by_id = {str(segment["id"]): segment for segment in segments if segment.get("id")}
    normalized: list[dict[str, Any]] = []
    for item in evidence:
        segment = segments_by_id.get(str(item.get("targetId", "")), {})
        normalized.append(
            {
                "targetId": str(item["targetId"]),
                "source": str(item["source"]),
                "summary": _normalize_evidence_summary(
                    source=str(item["source"]),
                    summary=str(item.get("summary") or ""),
                    segment=segment,
                ),
                "confidence": float(item.get("confidence", 0.75)),
            }
        )

    covered = {str(item["targetId"]) for item in normalized if item["source"] in {"asr", "shot_detection"}}
    for segment in segments:
        segment_id = str(segment["id"])
        if segment_id in covered:
            continue
        normalized.append(
            {
                "targetId": segment_id,
                "source": "shot_detection",
                "summary": f"{segment.get('startSec', 0.0)}-{segment.get('endSec', 0.0)} sec",
                "confidence": 0.75,
            }
        )
    return normalized


def _normalize_slot_role(role: str) -> str:
    normalized = _SLOT_ROLE_ALIASES.get(role, role)
    allowed = {
        "hook_visual",
        "hook_text",
        "product_closeup",
        "usage_scene",
        "benefit_card",
        "comparison",
        "proof",
        "transition",
        "cta",
    }
    return normalized if normalized in allowed else "usage_scene"


def _segment_times(
    segments: list[dict[str, Any]],
    *,
    duration_sec: float,
) -> list[dict[str, Any]]:
    if not segments:
        return segments

    normalized: list[dict[str, Any]] = []
    cta_indexes = [index for index, seg in enumerate(segments) if seg.get("role") == "cta"]
    cta_index = cta_indexes[-1] if cta_indexes else len(segments) - 1
    cta_start = max(0.0, duration_sec * 0.85) if duration_sec > 0 else 0.0

    body_count = max(len(segments) - (1 if cta_index == len(segments) - 1 else 0), 1)
    step = cta_start / body_count if body_count else duration_sec

    for index, segment in enumerate(segments):
        item = dict(segment)
        if item.get("startSec") is None or item.get("endSec") is None:
            if index == cta_index and index == len(segments) - 1:
                item["startSec"] = cta_start
                item["endSec"] = duration_sec
            else:
                item["startSec"] = step * index
                if index == cta_index:
                    item["endSec"] = duration_sec
                elif index + 1 == cta_index:
                    item["endSec"] = cta_start
                else:
                    item["endSec"] = step * (index + 1)
        item.setdefault("visualSummary", str(item.get("scriptSummary") or item.get("role") or "segment"))
        item.setdefault("intent", str(item.get("role") or "segment"))
        normalized.append(item)
    return normalized


def _normalize_shot_boundaries(
    shots: list[dict[str, Any]],
    *,
    rhythm: dict[str, Any],
) -> list[dict[str, Any]]:
    boundaries = rhythm.get("shotBoundaries", [])
    if boundaries and isinstance(boundaries[0], dict):
        normalized: list[dict[str, Any]] = []
        for item in boundaries:
            normalized.append(
                {
                    "startSec": float(item["startSec"]),
                    "endSec": float(item["endSec"]),
                    "confidence": float(item.get("confidence", 0.75)),
                    "changeReason": item.get("changeReason", "scene_change"),
                }
            )
        return normalized

    if shots:
        return [
            {
                "startSec": float(shot["startSec"]),
                "endSec": float(shot["endSec"]),
                "confidence": float(shot.get("confidence", 0.75)),
                "changeReason": shot.get("changeReason", "scene_change"),
            }
            for shot in shots
        ]

    if boundaries and isinstance(boundaries[0], (int, float)):
        starts = [float(value) for value in boundaries]
        end = starts[-1] if len(starts) == 1 else max(starts)
        return [
            {
                "startSec": starts[0],
                "endSec": end,
                "confidence": 0.75,
                "changeReason": "scene_change",
            }
        ]
    return []


def _normalize_slots(
    slots: list[dict[str, Any]],
    *,
    segments_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for slot in slots:
        segment_id = str(slot.get("segmentId", ""))
        segment = segments_by_id.get(segment_id, {})
        intent_text = str(slot.pop("intent", "") or slot.get("visualIntent") or segment.get("scriptSummary") or "slot")
        role = _normalize_slot_role(str(slot.get("role", "usage_scene")))
        normalized.append(
            {
                "id": str(slot.get("id") or f"{segment_id}-{role}"),
                "segmentId": segment_id,
                "role": role,
                "startSec": float(slot.get("startSec", segment.get("startSec", 0.0))),
                "endSec": float(slot.get("endSec", segment.get("endSec", 0.0))),
                "requiredAssetType": list(slot.get("requiredAssetType") or ["video", "image"]),
                "visualIntent": str(slot.get("visualIntent") or intent_text),
                "scriptIntent": str(slot.get("scriptIntent") or intent_text),
                "importance": str(slot.get("importance") or "recommended"),
                "constraints": list(slot.get("constraints") or []),
                **(
                    {"packagingHint": str(slot["packagingHint"])}
                    if slot.get("packagingHint")
                    else {}
                ),
            }
        )
    return normalized


def coerce_video_structure(
    payload: dict[str, Any],
    *,
    project_id: str,
    source_video_id: str,
    analysis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Best-effort normalization for near-miss LLM structure payloads."""
    analysis = analysis or {}
    metadata = dict(analysis.get("metadata") or payload.get("metadata") or {})
    if payload.get("durationSec") is not None and metadata.get("durationSec") is None:
        metadata["durationSec"] = payload["durationSec"]
    shots = list(analysis.get("shots") or [])
    duration_sec = float(metadata.get("durationSec") or payload.get("metadata", {}).get("durationSec") or 0.0)

    coerced: dict[str, Any] = {}
    coerced["id"] = str(payload.get("id") or f"video-structure-{project_id}")
    coerced["projectId"] = project_id
    coerced["sourceVideoId"] = source_video_id
    coerced["version"] = str(payload.get("version") or "p1-v1")

    clean_metadata = {
        key: metadata[key]
        for key in _ALLOWED_METADATA_KEYS
        if key in metadata
    }
    clean_metadata.setdefault("durationSec", duration_sec)
    clean_metadata.setdefault("hasAudio", True)
    coerced["metadata"] = clean_metadata

    narrative = dict(payload.get("narrative") or {})
    segments = _segment_times(list(narrative.get("segments") or []), duration_sec=duration_sec)
    narrative["segments"] = segments
    narrative.setdefault(
        "summary",
        " ".join(str(segment.get("scriptSummary", "")).strip() for segment in segments).strip()
        or "Sample video structure",
    )
    coerced["narrative"] = narrative
    segments_by_id = {str(segment["id"]): segment for segment in segments if segment.get("id")}

    rhythm_facts = _compute_rhythm_facts(shots, duration_sec=duration_sec or None)
    rhythm = dict(payload.get("rhythm") or {})
    boundaries = _normalize_shot_boundaries(shots, rhythm=rhythm)
    coerced["rhythm"] = {
        "totalDurationSec": float(rhythm_facts.get("durationSec", duration_sec)),
        "shotCount": int(rhythm_facts.get("shotCount", len(boundaries))),
        "avgShotDurationSec": float(rhythm_facts.get("avgShotDurationSec", 0.0)),
        "tempo": str(rhythm.get("tempo") or rhythm_facts.get("tempoHint") or "mixed"),
        "beatPoints": list(rhythm.get("beatPoints") or [0.0, duration_sec]),
        "shotBoundaries": boundaries,
    }

    packaging = dict(payload.get("packaging") or {})
    if not all(key in packaging for key in _DEFAULT_PACKAGING):
        packaging = dict(_DEFAULT_PACKAGING)
    coerced["packaging"] = {
        "titleCards": list(packaging.get("titleCards") or []),
        "stickers": list(packaging.get("stickers") or []),
        "transitions": list(packaging.get("transitions") or []),
        "visualDensity": str(packaging.get("visualDensity") or "medium"),
        **(
            {"subtitleStyle": dict(packaging["subtitleStyle"])}
            if isinstance(packaging.get("subtitleStyle"), dict)
            else {}
        ),
        **(
            {"coverStyle": dict(packaging["coverStyle"])}
            if isinstance(packaging.get("coverStyle"), dict)
            else {}
        ),
    }

    coerced["slots"] = _normalize_slots(list(payload.get("slots") or []), segments_by_id=segments_by_id)

    coerced["evidence"] = _ensure_segment_evidence(
        list(payload.get("evidence") or []),
        segments=segments,
    )
    coerced["confidence"] = float(payload.get("confidence", 0.75))
    return coerced
