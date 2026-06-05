from __future__ import annotations

import re
from pathlib import Path
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
_ALLOWED_TEMPOS = frozenset({"slow", "medium", "fast", "mixed"})
_TEMPO_ALIASES = {
    "moderate": "medium",
    "normal": "medium",
    "avg": "medium",
    "average": "medium",
    "steady": "medium",
    "quick": "fast",
    "rapid": "fast",
    "slow-paced": "slow",
    "fast-paced": "fast",
}


def _normalize_beat_points(
    beat_points: list[Any],
    *,
    duration_sec: float,
) -> list[float]:
    normalized: list[float] = []
    for item in beat_points:
        if isinstance(item, (int, float)):
            normalized.append(float(item))
            continue
        if isinstance(item, dict):
            time_sec = item.get("timeSec", item.get("time", item.get("sec")))
            if time_sec is not None:
                normalized.append(float(time_sec))
    if not normalized:
        return [0.0, duration_sec] if duration_sec > 0 else [0.0]
    normalized = sorted(set(max(0.0, value) for value in normalized))
    if duration_sec > 0 and normalized[-1] < duration_sec:
        normalized.append(duration_sec)
    return normalized


def _normalize_tempo(value: str | None, *, fallback: str = "mixed") -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        return fallback
    if raw in _ALLOWED_TEMPOS:
        return raw
    mapped = _TEMPO_ALIASES.get(raw)
    if mapped:
        return mapped
    return fallback


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

    durations = [
        float(shot.get("endSec", 0.0)) - float(shot.get("startSec", 0.0))
        for shot in shots
        if shot.get("endSec") is not None or shot.get("startSec") is not None
    ]
    if not durations and shots:
        durations = [1.0 for _ in shots]
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
        "durationSec": duration_sec if duration_sec is not None else float(shots[-1].get("endSec", 0.0)),
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
    analysis: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    segments_by_id = {str(segment["id"]): segment for segment in segments if segment.get("id")}
    normalized: list[dict[str, Any]] = []
    for item in evidence:
        if not isinstance(item, dict):
            continue
        target_id = str(item.get("targetId") or item.get("segmentId") or "").strip()
        if not target_id:
            time_range = item.get("timeRange")
            if isinstance(time_range, dict):
                midpoint = (
                    float(time_range.get("startSec", 0.0))
                    + float(time_range.get("endSec", 0.0))
                ) / 2.0
                for segment in segments:
                    if segment.get("id") is None:
                        continue
                    start_sec = float(segment.get("startSec", 0.0))
                    end_sec = float(segment.get("endSec", start_sec))
                    if start_sec <= midpoint <= end_sec:
                        target_id = str(segment["id"])
                        break
        if not target_id:
            continue
        segment = segments_by_id.get(target_id, {})
        source = str(item.get("source") or "shot_detection")
        summary = str(item.get("summary") or item.get("excerpt") or "").strip()
        if not summary:
            continue
        normalized.append(
            {
                "targetId": target_id,
                "source": source,
                "summary": _normalize_evidence_summary(
                    source=source,
                    summary=summary,
                    segment=segment,
                ),
                "confidence": float(item.get("confidence", 0.75)),
            }
        )

    audio_profile = analysis.get("audioProfile") if isinstance(analysis, dict) else None
    has_voiceover = isinstance(audio_profile, dict) and bool(audio_profile.get("hasVoiceover"))
    for segment in segments:
        segment_id = str(segment["id"])
        matches = [item for item in normalized if str(item.get("targetId")) == segment_id]
        if has_voiceover and not any(item.get("source") in {"asr", "audio"} for item in matches):
            excerpt = str(segment.get("transcriptExcerpt") or segment.get("scriptSummary") or "").strip()
            normalized.append(
                {
                    "targetId": segment_id,
                    "source": "asr",
                    "summary": f"{segment.get('startSec', 0.0)}-{segment.get('endSec', 0.0)} sec",
                    "confidence": 0.75,
                    **({"excerpt": excerpt} if excerpt else {}),
                }
            )
            continue
        if matches:
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


def _analysis_root_from_keyframes(analysis: dict[str, Any]) -> Path | None:
    keyframes = analysis.get("keyframes")
    if not isinstance(keyframes, list) or not keyframes:
        return None
    first = keyframes[0]
    if not isinstance(first, dict):
        return None
    raw_path = str(first.get("path", "")).strip()
    if not raw_path:
        return None
    path = Path(raw_path.replace("\\", "/"))
    parts = path.parts
    if "analysis" in parts:
        index = parts.index("analysis")
        return Path(*parts[: index + 1])
    return None


def _keyframe_relative_path(path_value: str, *, analysis_root: Path | None) -> str | None:
    raw = str(path_value).strip().replace("\\", "/")
    if not raw:
        return None
    if raw.startswith("keyframes/"):
        return raw
    candidate = Path(path_value)
    if candidate.is_file() and analysis_root is not None:
        try:
            return candidate.resolve().relative_to(analysis_root.resolve()).as_posix()
        except ValueError:
            pass
    marker = "/analysis/"
    if marker in raw:
        suffix = raw.split(marker, 1)[1]
        if suffix.startswith("keyframes/"):
            return suffix
    name = Path(raw).name
    return f"keyframes/{name}" if name else None


def _attach_keyframe_evidence(
    evidence: list[dict[str, Any]],
    *,
    segments: list[dict[str, Any]],
    keyframes: list[dict[str, Any]],
    analysis_root: Path | None,
) -> list[dict[str, Any]]:
    if not keyframes:
        return evidence

    has_keyframe = any(item.get("source") == "keyframe" for item in evidence)
    if has_keyframe:
        return evidence

    normalized = list(evidence)
    for segment in segments:
        segment_id = str(segment.get("id", ""))
        if not segment_id:
            continue
        start = float(segment.get("startSec", 0.0))
        end = float(segment.get("endSec", start))
        best: dict[str, Any] | None = None
        for frame in keyframes:
            if not isinstance(frame, dict):
                continue
            time_sec = float(frame.get("timeSec", -1.0))
            if time_sec < start or time_sec > end:
                continue
            score = float(frame.get("score", 0.0))
            if best is None or score > float(best.get("score", 0.0)):
                best = frame
        if best is None:
            midpoint = (start + end) / 2.0
            for frame in keyframes:
                if not isinstance(frame, dict):
                    continue
                distance = abs(float(frame.get("timeSec", 0.0)) - midpoint)
                score = float(frame.get("score", 0.0))
                if best is None:
                    best = {**frame, "_distance": distance}
                    continue
                best_distance = float(best.get("_distance", 1e9))
                if distance < best_distance or (distance == best_distance and score > float(best.get("score", 0.0))):
                    best = {**frame, "_distance": distance}
        if best is None:
            continue
        rel = _keyframe_relative_path(str(best.get("path", "")), analysis_root=analysis_root)
        if rel is None:
            continue
        normalized.append(
            {
                "targetId": segment_id,
                "source": "keyframe",
                "summary": rel,
                "confidence": min(0.99, max(0.5, float(best.get("score", 0.75)))),
            }
        )
    return normalized


def _normalize_slot_role(role: str) -> str:
    raw = str(role or "").strip()
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
    if raw in allowed:
        return raw
    normalized = _SLOT_ROLE_ALIASES.get(raw, raw)
    return normalized if normalized in allowed else "usage_scene"


_SEGMENT_ROLE_ALIASES = {
    "attention_grabber": "hook",
    "intro": "hook",
    "opening": "hook",
    "pain_point": "problem",
    "pain": "problem",
    "product_intro": "solution",
    "solution_visual": "solution",
    "benefit": "benefit",
    "call_to_action": "cta",
    "cta_visual": "cta",
    "outro": "cta",
}
_ALLOWED_SEGMENT_ROLES = frozenset(
    {"hook", "problem", "solution", "proof", "benefit", "comparison", "cta", "transition"}
)


def _normalize_segment_role(role: str) -> str:
    raw = str(role or "hook").strip().lower()
    if raw in _ALLOWED_SEGMENT_ROLES:
        return raw
    slug = re.sub(r"[^a-z0-9]+", "_", raw).strip("_")
    if slug in _SEGMENT_ROLE_ALIASES:
        return _SEGMENT_ROLE_ALIASES[slug]
    if slug in _ALLOWED_SEGMENT_ROLES:
        return slug
    if any(token in raw for token in ("hook", "opening", "intro", "开场", "钩子")):
        return "hook"
    if any(token in raw for token in ("problem", "pain", "challenge", "痛点", "问题")):
        return "problem"
    if any(token in raw for token in ("solution", "explain", "practice", "how to", "方案", "解决")):
        return "solution"
    if any(
        token in raw
        for token in ("proof", "evidence", "research", "anecdote", "analysis", "bias", "fail", "证言", "证据")
    ):
        return "proof"
    if any(token in raw for token in ("benefit", "implication", "value", "利益", "好处")):
        return "benefit"
    if any(token in raw for token in ("comparison", "versus", " vs ", "对比")):
        return "comparison"
    if any(token in raw for token in ("cta", "call to action", "closing", "行动号召", "下单")):
        return "cta"
    if "transition" in raw or "转场" in raw:
        return "transition"
    return _SEGMENT_ROLE_ALIASES.get(raw, "hook")


def _normalize_narrative_segment(segment: dict[str, Any], *, index: int) -> dict[str, Any]:
    item = dict(segment)
    item.pop("textOverlay", None)
    item.pop("text_overlay", None)
    if item.get("startSec") is None and item.get("startTimeSec") is not None:
        item["startSec"] = item.pop("startTimeSec")
    if item.get("endSec") is None and item.get("endTimeSec") is not None:
        item["endSec"] = item.pop("endTimeSec")
    item.pop("startTimeSec", None)
    item.pop("endTimeSec", None)

    role = _normalize_segment_role(str(item.get("role") or "hook"))
    script = str(
        item.get("scriptSummary")
        or item.get("transcriptExcerpt")
        or item.get("script")
        or item.get("narration")
        or item.get("text")
        or role
    ).strip()
    visual_spec = item.get("visualSpec")
    visual_from_spec = ""
    if isinstance(visual_spec, dict):
        parts = [
            str(visual_spec.get("framing") or "").strip(),
            str(visual_spec.get("subject") or "").strip(),
            str(visual_spec.get("cameraMove") or "").strip(),
        ]
        visual_from_spec = "，".join(part for part in parts if part)
    visual = str(item.get("visualSummary") or item.get("visual") or visual_from_spec or script or role).strip()
    intent = str(item.get("intent") or visual or role).strip()
    normalized = {
        "id": str(item.get("id") or f"segment-{index + 1}"),
        "role": role,
        "startSec": item.get("startSec"),
        "endSec": item.get("endSec"),
        "scriptSummary": script,
        "visualSummary": visual,
        "intent": intent,
    }
    for key in (
        "transcriptExcerpt",
        "rhetoricalDevices",
        "emotionTone",
        "retentionRole",
        "voStyle",
        "visualSpec",
    ):
        if item.get(key) is not None:
            normalized[key] = item[key]
    return normalized


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


_CHANGE_REASON_ALIASES = {
    "histogram_cut": "visual_cut",
    "hard_cut": "visual_cut",
    "cut": "visual_cut",
}


def _normalize_change_reason(value: Any) -> str:
    raw = str(value or "scene_change").strip()
    mapped = _CHANGE_REASON_ALIASES.get(raw, raw)
    if mapped in {"visual_cut", "scene_change", "caption_change", "beat", "unknown"}:
        return mapped
    return "unknown"


def _normalize_shot_boundaries(
    shots: list[dict[str, Any]],
    *,
    rhythm: dict[str, Any],
) -> list[dict[str, Any]]:
    boundaries = rhythm.get("shotBoundaries", [])
    if boundaries and isinstance(boundaries[0], dict):
        normalized: list[dict[str, Any]] = []
        for item in boundaries:
            start = float(item.get("startSec", 0.0))
            end_raw = item.get("endSec")
            end = float(end_raw if end_raw is not None else start + 0.5)
            if end <= start:
                end = start + 0.5
            normalized.append(
                {
                    "startSec": start,
                    "endSec": end,
                    "confidence": float(item.get("confidence", 0.75)),
                    "changeReason": _normalize_change_reason(item.get("changeReason", "scene_change")),
                }
            )
        return normalized

    if shots:
        normalized_shots: list[dict[str, Any]] = []
        cursor = 0.0
        for shot in shots:
            start = float(shot.get("startSec", cursor))
            end_raw = shot.get("endSec")
            end = float(end_raw if end_raw is not None else max(start + 0.5, cursor + 0.5))
            if end <= start:
                end = start + 0.5
            normalized_shots.append(
                {
                    "startSec": start,
                    "endSec": end,
                    "confidence": float(shot.get("confidence", 0.75)),
                    "changeReason": _normalize_change_reason(shot.get("changeReason", "scene_change")),
                }
            )
            cursor = end
        return normalized_shots

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
        slot_payload: dict[str, Any] = {
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
        if slot.get("durationSharePct") is not None:
            share = float(slot["durationSharePct"])
            if share > 1.0:
                share = share / 100.0
            slot_payload["durationSharePct"] = max(0.0, min(1.0, share))
        migration = str(slot.get("migrationTemplate") or "").strip()
        if migration:
            slot_payload["migrationTemplate"] = migration
        packaging_requirements_raw = slot.get("packagingRequirements")
        if isinstance(packaging_requirements_raw, str) and packaging_requirements_raw.strip():
            packaging_requirements = [packaging_requirements_raw.strip()]
        else:
            packaging_requirements = list(packaging_requirements_raw or [])
        if packaging_requirements:
            slot_payload["packagingRequirements"] = packaging_requirements
        anti_patterns_raw = slot.get("antiPatterns")
        if isinstance(anti_patterns_raw, str) and anti_patterns_raw.strip():
            anti_patterns = [anti_patterns_raw.strip()]
        else:
            anti_patterns = list(anti_patterns_raw or [])
        if anti_patterns:
            slot_payload["antiPatterns"] = anti_patterns
        normalized.append(slot_payload)
    return normalized


def _payload_has_v2_deep_fields(payload: dict[str, Any]) -> bool:
    narrative = payload.get("narrative") if isinstance(payload.get("narrative"), dict) else {}
    for segment in narrative.get("segments") or []:
        if not isinstance(segment, dict):
            continue
        if any(
            segment.get(key)
            for key in (
                "transcriptExcerpt",
                "voStyle",
                "visualSpec",
                "rhetoricalDevices",
                "emotionTone",
            )
        ):
            return True
    for slot in payload.get("slots") or []:
        if not isinstance(slot, dict):
            continue
        if slot.get("migrationTemplate") or slot.get("packagingRequirements"):
            return True
    explicit = str(payload.get("version") or "").strip()
    return explicit.startswith("p1-v2")


def _resolve_structure_version(payload: dict[str, Any]) -> str:
    explicit = str(payload.get("version") or "").strip()
    if explicit:
        return explicit
    if _payload_has_v2_deep_fields(payload):
        return "p1-v2"
    return "p0-v1"


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
    coerced["version"] = _resolve_structure_version(payload)

    clean_metadata = {
        key: metadata[key]
        for key in _ALLOWED_METADATA_KEYS
        if key in metadata
    }
    clean_metadata.setdefault("durationSec", duration_sec)
    clean_metadata.setdefault("hasAudio", True)
    coerced["metadata"] = clean_metadata

    narrative = dict(payload.get("narrative") or {})
    if not narrative.get("segments") and isinstance(payload.get("segments"), list):
        narrative["segments"] = payload["segments"]
    narrative.pop("intent", None)
    raw_segments = [
        _normalize_narrative_segment(segment, index=index)
        for index, segment in enumerate(list(narrative.get("segments") or []))
    ]
    segments = _segment_times(raw_segments, duration_sec=duration_sec)
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
        "tempo": _normalize_tempo(
            str(rhythm.get("tempo") or rhythm_facts.get("tempoHint") or "mixed"),
            fallback="mixed",
        ),
        "beatPoints": _normalize_beat_points(
            list(rhythm.get("beatPoints") or [0.0, duration_sec]),
            duration_sec=duration_sec,
        ),
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
    }

    coerced["slots"] = _normalize_slots(list(payload.get("slots") or []), segments_by_id=segments_by_id)

    coerced["evidence"] = _attach_keyframe_evidence(
        _ensure_segment_evidence(
            list(payload.get("evidence") or []),
            segments=segments,
            analysis=analysis,
        ),
        segments=segments,
        keyframes=list(analysis.get("keyframes") or []),
        analysis_root=_analysis_root_from_keyframes(analysis),
    )
    coerced["confidence"] = float(payload.get("confidence", 0.75))
    return coerced
