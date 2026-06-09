from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from structure.slot_roles import default_required_asset_types, normalize_slot_role

_ALLOWED_METADATA_KEYS = frozenset(
    {"durationSec", "width", "height", "fps", "codec", "hasAudio"}
)
_ASR_RANGE_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*(?:to|-)\s*(\d+(?:\.\d+)?)")
_SHOT_BOUNDARY_PATTERN = re.compile(r"\d+(?:\.\d+)?")
_LOW_VALUE_EVIDENCE_PATTERN = re.compile(r"\d+\s+overlapping\s+shot\s+boundaries", re.IGNORECASE)
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


def _resolve_beat_points(
    rhythm: dict[str, Any],
    *,
    analysis: dict[str, Any],
    segments: list[dict[str, Any]],
    duration_sec: float,
) -> list[float]:
    """Narrative/onset beats — never mirror raw shot cut starts."""
    explicit = [
        float(value)
        for value in (rhythm.get("beatPoints") or [])
        if isinstance(value, (int, float))
    ]
    if explicit:
        return _normalize_beat_points(explicit, duration_sec=duration_sec)

    audio_profile = analysis.get("audioProfile")
    if isinstance(audio_profile, dict):
        onset_times = [
            float(value)
            for value in (audio_profile.get("onsetTimes") or [])
            if isinstance(value, (int, float))
        ]
        if onset_times:
            return _normalize_beat_points(onset_times[:12], duration_sec=duration_sec)

    narrative_beats: list[float] = [0.0]
    for segment in segments:
        if not isinstance(segment, dict):
            continue
        start = segment.get("startSec")
        if isinstance(start, (int, float)) and float(start) > 0:
            narrative_beats.append(float(start))
    if duration_sec > 0:
        narrative_beats.append(duration_sec)
    return _normalize_beat_points(narrative_beats, duration_sec=duration_sec)


def _sanitize_evidence_summary(summary: str, *, segment: dict[str, Any]) -> str:
    text = str(summary or "").strip()
    if _LOW_VALUE_EVIDENCE_PATTERN.search(text):
        return f"{segment.get('startSec', 0.0)}-{segment.get('endSec', 0.0)} sec"
    return text


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
        summary = _sanitize_evidence_summary(
            str(item.get("summary") or item.get("excerpt") or "").strip(),
            segment=segment,
        )
        if not summary:
            continue
        entry: dict[str, Any] = {
            "targetId": target_id,
            "source": source,
            "summary": _normalize_evidence_summary(
                source=source,
                summary=summary,
                segment=segment,
            ),
            "confidence": float(item.get("confidence", 0.75)),
        }
        excerpt = str(item.get("excerpt") or "").strip()
        if excerpt:
            entry["excerpt"] = excerpt
        time_range = item.get("timeRange")
        if isinstance(time_range, dict):
            entry["timeRange"] = time_range
        normalized.append(entry)

    audio_profile = analysis.get("audioProfile") if isinstance(analysis, dict) else None
    has_voiceover = isinstance(audio_profile, dict) and bool(audio_profile.get("hasVoiceover"))
    for segment in segments:
        segment_id = str(segment["id"])
        matches = [item for item in normalized if str(item.get("targetId")) == segment_id]
        if has_voiceover and not any(item.get("source") in {"asr", "audio"} for item in matches):
            excerpt = str(segment.get("transcriptExcerpt") or "").strip()
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
    return normalize_slot_role(role)


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
        legacy_intent = str(slot.pop("intent", "") or "").strip()
        visual_intent = str(slot.get("visualIntent") or "").strip()
        script_intent = str(slot.get("scriptIntent") or "").strip()
        if not visual_intent:
            visual_intent = str(
                segment.get("visualSummary") or legacy_intent or segment.get("intent") or "画面呈现"
            ).strip()
        if not script_intent:
            script_intent = str(
                segment.get("scriptSummary") or legacy_intent or segment.get("intent") or "口播表达"
            ).strip()
        if visual_intent == script_intent:
            seg_visual = str(segment.get("visualSummary") or "").strip()
            seg_script = str(segment.get("scriptSummary") or "").strip()
            if seg_visual and seg_script and seg_visual != seg_script:
                visual_intent = seg_visual
                script_intent = seg_script
            elif seg_visual and visual_intent != seg_visual:
                visual_intent = seg_visual
            elif seg_script and script_intent != seg_script:
                script_intent = seg_script
        raw_slot_role = str(slot.get("role", "")).strip()
        if raw_slot_role:
            role = _normalize_slot_role(raw_slot_role)
        elif segment.get("role"):
            role = _normalize_slot_role(str(segment.get("role")))
        else:
            role = "usage_scene"
        slot_payload: dict[str, Any] = {
                "id": str(slot.get("id") or f"{segment_id}-{role}"),
                "segmentId": segment_id,
                "role": role,
                "startSec": float(slot.get("startSec", segment.get("startSec", 0.0))),
                "endSec": float(slot.get("endSec", segment.get("endSec", 0.0))),
                "requiredAssetType": list(
                    slot.get("requiredAssetType")
                    or default_required_asset_types(role)
                ),
                "visualIntent": visual_intent,
                "scriptIntent": script_intent,
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


def _ensure_transcript_excerpts(
    segments: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
) -> None:
    evidence_by_target: dict[str, list[dict[str, Any]]] = {}
    for item in evidence:
        if not isinstance(item, dict):
            continue
        target_id = str(item.get("targetId") or "")
        if target_id:
            evidence_by_target.setdefault(target_id, []).append(item)

    for segment in segments:
        if not isinstance(segment, dict):
            continue
        if len(str(segment.get("transcriptExcerpt") or "").strip()) >= 4:
            continue
        segment_id = str(segment.get("id") or "")
        excerpt = ""
        for item in evidence_by_target.get(segment_id, []):
            if item.get("source") == "asr" and item.get("excerpt"):
                excerpt = str(item["excerpt"]).strip()
                break
        if len(excerpt) < 4:
            continue
        if excerpt:
            segment["transcriptExcerpt"] = excerpt[:120]


def _build_outline_timeline(segments: list[dict[str, Any]], *, duration_sec: float) -> list[dict[str, Any]]:
    timeline: list[dict[str, Any]] = []
    for segment in segments:
        if not isinstance(segment, dict):
            continue
        start = float(segment.get("startSec", 0.0))
        end = float(segment.get("endSec", start))
        span = max(0.0, end - start)
        share = span / duration_sec if duration_sec > 0 else 0.0
        timeline.append(
            {
                "phase": str(segment.get("role") or "segment"),
                "startSec": start,
                "endSec": end,
                "sharePct": round(min(1.0, max(0.0, share)), 3),
            }
        )
    return timeline


def _build_cut_rate_profile(
    *,
    rhythm: dict[str, Any],
    shots: list[dict[str, Any]],
    duration_sec: float,
) -> dict[str, Any]:
    avg_shot = float(rhythm.get("avgShotDurationSec") or 0.0)
    opening_cut_rate = "medium"
    if shots and duration_sec > 0:
        opening_shots = [s for s in shots if float(s.get("startSec", 0.0)) < min(5.0, duration_sec * 0.2)]
        if opening_shots:
            opening_avg = sum(
                float(s.get("endSec", 0.0)) - float(s.get("startSec", 0.0)) for s in opening_shots
            ) / len(opening_shots)
            if opening_avg < 1.2:
                opening_cut_rate = "fast"
            elif opening_avg > 2.5:
                opening_cut_rate = "slow"
    fast_ranges: list[dict[str, Any]] = []
    for shot in shots[:6]:
        start = float(shot.get("startSec", 0.0))
        end = float(shot.get("endSec", start))
        if end - start < 1.0:
            fast_ranges.append({"startSec": start, "endSec": end})
    return {
        "avgShotSec": round(avg_shot, 3),
        "openingCutRate": opening_cut_rate,
        "fastCutRanges": fast_ranges[:5],
    }


def _normalize_share_pct(value: Any) -> float:
    share = float(value)
    if share > 1.0:
        share = share / 100.0
    return round(min(1.0, max(0.0, share)), 3)


def _normalize_outline_timeline(
    timeline: Any,
    *,
    segments: list[dict[str, Any]],
    duration_sec: float,
) -> list[dict[str, Any]]:
    if not isinstance(timeline, list) or not timeline:
        return _build_outline_timeline(segments, duration_sec=duration_sec)
    normalized: list[dict[str, Any]] = []
    for item in timeline:
        if not isinstance(item, dict):
            continue
        if "startSec" not in item and "endSec" not in item and "sharePct" not in item:
            continue
        start = float(item.get("startSec", 0.0))
        end = float(item.get("endSec", start))
        share_raw = item.get("sharePct")
        if share_raw is None and duration_sec > 0:
            share = max(0.0, end - start) / duration_sec
        else:
            share = _normalize_share_pct(share_raw or 0.0)
        normalized.append(
            {
                "phase": str(item.get("phase") or item.get("nodeName") or "segment"),
                "startSec": start,
                "endSec": end,
                "sharePct": share,
            }
        )
    if not normalized:
        return _build_outline_timeline(segments, duration_sec=duration_sec)
    return normalized


def _normalize_emotion_triggers(
    triggers: Any,
    *,
    segments: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not isinstance(triggers, list) or not triggers:
        return []
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(triggers):
        if isinstance(item, str):
            segment = segments[index] if index < len(segments) else {}
            if not isinstance(segment, dict):
                segment = segments[0] if segments and isinstance(segments[0], dict) else {}
            label, _, mechanism = item.partition("：")
            normalized.append(
                {
                    "timeSec": float(segment.get("startSec", 0.0) if isinstance(segment, dict) else 0.0),
                    "triggerType": label[:40] or "emotion",
                    "segmentId": str(segment.get("id", "") if isinstance(segment, dict) else ""),
                    "mechanism": (mechanism or item)[:80],
                }
            )
            continue
        if not isinstance(item, dict):
            continue
        if all(key in item for key in ("timeSec", "triggerType", "segmentId", "mechanism")):
            normalized.append(
                {
                    "timeSec": float(item.get("timeSec", 0.0)),
                    "triggerType": str(item.get("triggerType") or "beat"),
                    "segmentId": str(item.get("segmentId") or ""),
                    "mechanism": str(item.get("mechanism") or "")[:80],
                }
            )
            continue
        segment = segments[index] if index < len(segments) else {}
        if not isinstance(segment, dict):
            segment = segments[0] if segments and isinstance(segments[0], dict) else {}
        normalized.append(
            {
                "timeSec": float(segment.get("startSec", 0.0) if isinstance(segment, dict) else 0.0),
                "triggerType": str(item.get("type") or item.get("triggerType") or "beat"),
                "segmentId": str(segment.get("id", "") if isinstance(segment, dict) else ""),
                "mechanism": str(item.get("desc") or item.get("mechanism") or item.get("type") or "")[
                    :80
                ],
            }
        )
    return normalized


def _normalize_vo_profile(
    profile: Any,
    *,
    rhythm: dict[str, Any],
    metrics: dict[str, Any],
    duration_sec: float,
    segments: list[dict[str, Any]],
) -> dict[str, Any]:
    raw = dict(profile) if isinstance(profile, dict) else {}
    style_text = str(raw.pop("style", "") or "").strip()
    vo_profile: dict[str, Any] = {
        key: raw[key]
        for key in ("pace", "energy", "persona", "wordsPerMinute")
        if key in raw
    }
    vo_profile.setdefault("pace", str(raw.get("pace") or rhythm.get("tempo") or "medium")[:40])
    vo_profile.setdefault("energy", str(raw.get("energy") or "medium")[:40])
    vo_profile.setdefault(
        "persona",
        str(vo_profile.get("persona") or style_text or "口播讲解")[:80],
    )
    if metrics.get("voiceoverCoveragePct") is not None and duration_sec > 0:
        speech_sec = float(metrics["voiceoverCoveragePct"]) * duration_sec
        words = sum(len(str(s.get("scriptSummary", ""))) for s in segments if isinstance(s, dict))
        if speech_sec > 0 and words > 0 and "wordsPerMinute" not in vo_profile:
            vo_profile["wordsPerMinute"] = round(words / (speech_sec / 60.0), 1)
    return vo_profile


def _normalize_cut_rate_profile(
    profile: Any,
    *,
    rhythm: dict[str, Any],
    shots: list[dict[str, Any]],
    duration_sec: float,
) -> dict[str, Any]:
    if isinstance(profile, str):
        return _build_cut_rate_profile(rhythm=rhythm, shots=shots, duration_sec=duration_sec)
    if not isinstance(profile, dict) or not profile:
        return _build_cut_rate_profile(rhythm=rhythm, shots=shots, duration_sec=duration_sec)
    normalized: dict[str, Any] = {}
    if profile.get("avgShotSec") is not None:
        normalized["avgShotSec"] = float(profile["avgShotSec"])
    elif profile.get("avgShotDurationSec") is not None:
        normalized["avgShotSec"] = float(profile["avgShotDurationSec"])
    if profile.get("openingCutRate") is not None:
        normalized["openingCutRate"] = str(profile["openingCutRate"])
    fast_ranges = profile.get("fastCutRanges")
    if isinstance(fast_ranges, list):
        cleaned: list[dict[str, Any]] = []
        for item in fast_ranges:
            if not isinstance(item, dict):
                continue
            cleaned.append(
                {
                    "startSec": float(item.get("startSec", 0.0)),
                    "endSec": float(item.get("endSec", item.get("startSec", 0.0))),
                }
            )
        normalized["fastCutRanges"] = cleaned[:5]
    if normalized.get("avgShotSec") is None:
        return _build_cut_rate_profile(rhythm=rhythm, shots=shots, duration_sec=duration_sec)
    normalized.setdefault("openingCutRate", "medium")
    normalized.setdefault("fastCutRanges", [])
    return normalized


def _cap_list(items: list[Any], *, limit: int) -> list[Any]:
    return list(items[:limit]) if len(items) > limit else list(items)


def _enrich_v3_blocks(
    coerced: dict[str, Any],
    *,
    payload: dict[str, Any],
    analysis: dict[str, Any],
) -> None:
    """Deterministic v3 block fill (L2) and version upgrade."""
    segments = list(coerced.get("narrative", {}).get("segments") or [])
    rhythm = coerced.get("rhythm") if isinstance(coerced.get("rhythm"), dict) else {}
    duration_sec = float(coerced.get("metadata", {}).get("durationSec") or 0.0)
    shots = list(analysis.get("shots") or [])
    narrative_summary = str(coerced.get("narrative", {}).get("summary") or "").strip()

    for segment in segments:
        if isinstance(segment, dict):
            segment.pop("retentionRole", None)

    packaging = coerced.pop("packaging", None)
    if not isinstance(packaging, dict):
        packaging = payload.get("packaging") if isinstance(payload.get("packaging"), dict) else {}
    visual_density = str(packaging.get("visualDensity") or "medium")

    context = dict(payload.get("context") or coerced.get("context") or {})
    context.setdefault("contentCategory", "general")
    context.setdefault("platformFormat", "9:16_short")
    context.setdefault("primaryIntent", "exposure")
    context.setdefault("successHypothesis", narrative_summary[:160] or "结构迁移可提升完播与转化")
    context.setdefault(
        "applicability",
        {"suitableFor": ["短视频"], "unsuitableFor": ["长纪录片"]},
    )

    hook_segment = next((s for s in segments if s.get("role") == "hook"), segments[0] if segments else {})
    verbal = dict(payload.get("verbal") or coerced.get("verbal") or {})
    verbal.setdefault(
        "hookTemplate",
        str(verbal.get("hookTemplate") or hook_segment.get("scriptSummary") or "反问/痛点开场")[:120],
    )
    verbal["outlineTimeline"] = _normalize_outline_timeline(
        verbal.get("outlineTimeline"),
        segments=segments,
        duration_sec=duration_sec,
    )
    verbal.setdefault("ctaMechanism", str(verbal.get("ctaMechanism") or "结尾明确行动号召")[:120])
    verbal = {
        key: verbal[key]
        for key in ("hookTemplate", "outlineTimeline", "ctaMechanism", "infoLubricantRatio")
        if key in verbal
    }

    visual = dict(payload.get("visual") or coerced.get("visual") or {})
    misplaced_vo = visual.pop("voProfile", None)
    visual_summary = visual.pop("summary", None)
    visual["cutRateProfile"] = _normalize_cut_rate_profile(
        visual.get("cutRateProfile"),
        rhythm=rhythm,
        shots=shots,
        duration_sec=duration_sec,
    )
    packaging_spec = dict(visual.get("packagingSpec") or {})
    packaging_spec.setdefault("visualDensity", visual_density)
    if visual_summary:
        packaging_spec.setdefault("summary", str(visual_summary)[:200])
    elif not packaging_spec.get("summary"):
        packaging_spec.setdefault("summary", f"字幕密度{visual_density}，花字/贴纸随节奏点缀")
    visual["packagingSpec"] = packaging_spec
    if visual.get("conceptVisualMap"):
        visual["conceptVisualMap"] = _cap_list(list(visual["conceptVisualMap"]), limit=8)
    visual = {
        key: visual[key]
        for key in ("conceptVisualMap", "cutRateProfile", "packagingSpec")
        if key in visual
    }

    audio_profile = analysis.get("audioProfile") if isinstance(analysis.get("audioProfile"), dict) else {}
    audio = dict(payload.get("audio") or coerced.get("audio") or {})
    metrics = audio_profile.get("metrics") if isinstance(audio_profile.get("metrics"), dict) else {}
    vo_seed: dict[str, Any] = {}
    if isinstance(audio.get("voProfile"), dict):
        vo_seed.update(audio["voProfile"])
    elif isinstance(misplaced_vo, str) and misplaced_vo.strip():
        vo_seed["style"] = misplaced_vo.strip()
    audio["voProfile"] = _normalize_vo_profile(
        vo_seed,
        rhythm=rhythm,
        metrics=metrics,
        duration_sec=duration_sec,
        segments=segments,
    )
    audio = {
        key: audio[key]
        for key in ("voProfile", "audioEventRules")
        if key in audio
    }
    if audio.get("audioEventRules"):
        audio["audioEventRules"] = _cap_list(list(audio["audioEventRules"]), limit=5)

    transfer = dict(payload.get("transfer") or coerced.get("transfer") or {})
    transfer.setdefault("structureFamily", "short_form_segmented")
    transfer.setdefault(
        "differentiationLever",
        str(transfer.get("differentiationLever") or narrative_summary[:120] or "叙事节奏+证据链组合"),
    )
    normalized_triggers = _normalize_emotion_triggers(
        transfer.get("emotionTriggers"),
        segments=segments,
    )
    if normalized_triggers:
        transfer["emotionTriggers"] = _cap_list(normalized_triggers, limit=5)
    else:
        triggers: list[dict[str, Any]] = []
        for segment in segments[:5]:
            if not isinstance(segment, dict):
                continue
            triggers.append(
                {
                    "timeSec": float(segment.get("startSec", 0.0)),
                    "triggerType": str(segment.get("role") or "beat"),
                    "segmentId": str(segment.get("id") or ""),
                    "mechanism": str(segment.get("intent") or segment.get("role") or "")[:80],
                }
            )
        transfer["emotionTriggers"] = triggers
    transfer.setdefault("scalabilityRules", "保持段级意图与槽位一一对应，可替换素材复用结构")
    transfer.setdefault("nonTransferableElements", ["具体产品名称", "真人面孔"])

    analysis_quality = dict(coerced.get("analysisQuality") or payload.get("analysisQuality") or {})
    analysis_quality.setdefault("locale", str(analysis.get("locale") or "zh"))
    analysis_quality.setdefault("promoteReady", False)
    analysis_quality.setdefault("warnings", list(analysis_quality.get("warnings") or []))
    route = str(analysis.get("structureAnalysisRoute") or "")
    if route == "direct_multimodal":
        warnings = list(analysis_quality.get("warnings") or [])
        if "direct_route_partial_v3" not in warnings:
            warnings.append("direct_route_partial_v3")
        analysis_quality["warnings"] = warnings

    coerced["context"] = context
    coerced["verbal"] = verbal
    coerced["visual"] = visual
    coerced["audio"] = audio
    coerced["transfer"] = transfer
    coerced["analysisQuality"] = analysis_quality
    coerced["version"] = "p1-v3"


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
    coerced["version"] = "p1-v3"

    clean_metadata = {
        key: metadata[key]
        for key in _ALLOWED_METADATA_KEYS
        if key in metadata
    }
    clean_metadata.setdefault("durationSec", duration_sec)
    clean_metadata.setdefault("hasAudio", True)
    coerced["metadata"] = clean_metadata

    narrative = dict(payload.get("narrative") or {})
    nested_evidence = narrative.pop("evidence", None)
    evidence_seed = list(payload.get("evidence") or [])
    if isinstance(nested_evidence, list):
        evidence_seed.extend(item for item in nested_evidence if isinstance(item, dict))
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
    route = str(analysis.get("structureAnalysisRoute") or "")
    if route == "direct_multimodal":
        boundaries = _normalize_shot_boundaries(shots, rhythm={})
        tempo = _normalize_tempo(
            str(rhythm.get("tempo") or rhythm_facts.get("tempoHint") or "mixed"),
            fallback=str(rhythm_facts.get("tempoHint") or "mixed"),
        )
    else:
        boundaries = _normalize_shot_boundaries(shots, rhythm=rhythm)
        tempo = _normalize_tempo(
            str(rhythm.get("tempo") or rhythm_facts.get("tempoHint") or "mixed"),
            fallback="mixed",
        )
    beat_points = _resolve_beat_points(
        rhythm,
        analysis=analysis,
        segments=segments,
        duration_sec=duration_sec,
    )
    coerced["rhythm"] = {
        "totalDurationSec": float(rhythm_facts.get("durationSec", duration_sec)),
        "shotCount": int(rhythm_facts.get("shotCount", len(boundaries))),
        "avgShotDurationSec": float(rhythm_facts.get("avgShotDurationSec", 0.0)),
        "tempo": tempo,
        "beatPoints": beat_points[:12],
        "shotBoundaries": boundaries,
    }

    coerced["slots"] = _normalize_slots(list(payload.get("slots") or []), segments_by_id=segments_by_id)

    coerced["evidence"] = _attach_keyframe_evidence(
        _ensure_segment_evidence(
            evidence_seed,
            segments=segments,
            analysis=analysis,
        ),
        segments=segments,
        keyframes=list(analysis.get("keyframes") or []),
        analysis_root=_analysis_root_from_keyframes(analysis),
    )
    _ensure_transcript_excerpts(segments, coerced["evidence"])
    coerced["narrative"]["segments"] = segments
    coerced["confidence"] = float(payload.get("confidence", 0.75))
    _enrich_v3_blocks(coerced, payload=payload, analysis=analysis)
    return coerced
