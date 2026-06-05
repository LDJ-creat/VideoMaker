from __future__ import annotations

from typing import Any


def extract_slot_pattern(structure: dict[str, Any]) -> str:
    narrative = structure.get("narrative") if isinstance(structure.get("narrative"), dict) else {}
    segments = narrative.get("segments") if isinstance(narrative.get("segments"), list) else []
    roles: list[str] = []
    for segment in segments:
        if not isinstance(segment, dict):
            continue
        role = str(segment.get("role", "")).strip()
        if not role or role == "transition":
            continue
        if not roles or roles[-1] != role:
            roles.append(role)
    if not roles:
        slots = structure.get("slots") if isinstance(structure.get("slots"), list) else []
        for slot in slots:
            if isinstance(slot, dict) and slot.get("role"):
                role = str(slot["role"])
                if not roles or roles[-1] != role:
                    roles.append(role)
    return "→".join(roles) if roles else "unknown"


def duration_bucket(duration_sec: float) -> str:
    if duration_sec <= 20:
        return "15s"
    if duration_sec <= 45:
        return "30s"
    if duration_sec <= 75:
        return "60s"
    return "60s+"


def infer_hook_type(structure: dict[str, Any]) -> str | None:
    narrative = structure.get("narrative") if isinstance(structure.get("narrative"), dict) else {}
    segments = narrative.get("segments") if isinstance(narrative.get("segments"), list) else []
    hook_text = ""
    for segment in segments:
        if isinstance(segment, dict) and segment.get("role") == "hook":
            hook_text = " ".join(
                str(segment.get(key, ""))
                for key in ("scriptSummary", "visualSummary", "intent")
            ).lower()
            break
    if not hook_text:
        summary = str(narrative.get("summary", "")).lower()
        hook_text = summary
    if any(token in hook_text for token in ("?", "吗", "pain", "痛点", "麻烦", "贵")):
        return "pain_point"
    if any(token in hook_text for token in ("结果", "效果", "立刻", "马上")):
        return "result"
    if any(token in hook_text for token in ("没想到", "竟然", "secret", "悬念")):
        return "suspense"
    return None


def build_entry_meta(
    structure: dict[str, Any],
    *,
    title: str,
    category: str,
    style: str,
    summary: str,
    hook_type: str | None = None,
    sample_analysis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metadata = structure.get("metadata") if isinstance(structure.get("metadata"), dict) else {}
    rhythm = structure.get("rhythm") if isinstance(structure.get("rhythm"), dict) else {}
    duration_sec = float(metadata.get("durationSec", 0.0) or 0.0)
    tempo = rhythm.get("tempo")
    narrative = structure.get("narrative") if isinstance(structure.get("narrative"), dict) else {}
    segments = narrative.get("segments") if isinstance(narrative.get("segments"), list) else []
    hook_segment = next(
        (segment for segment in segments if isinstance(segment, dict) and segment.get("role") == "hook"),
        segments[0] if segments else {},
    )
    vo_style = hook_segment.get("voStyle") if isinstance(hook_segment, dict) else {}
    visual_spec = hook_segment.get("visualSpec") if isinstance(hook_segment, dict) else {}
    rhetorical = hook_segment.get("rhetoricalDevices") if isinstance(hook_segment, dict) else []
    has_bgm = False
    if isinstance(sample_analysis, dict):
        audio_profile = sample_analysis.get("audioProfile")
        if isinstance(audio_profile, dict):
            has_bgm = bool(audio_profile.get("hasBgm"))
    return {
        "title": title,
        "category": category,
        "style": style,
        "summary": summary,
        "hookType": hook_type or infer_hook_type(structure),
        "tempo": tempo if tempo in {"slow", "medium", "fast", "mixed"} else None,
        "durationBucket": duration_bucket(duration_sec) if duration_sec > 0 else None,
        "slotPattern": extract_slot_pattern(structure),
        "visualStyle": visual_spec.get("colorMood") if isinstance(visual_spec, dict) else None,
        "voPersona": vo_style.get("persona") if isinstance(vo_style, dict) else None,
        "hasBgm": has_bgm,
        "rhetoricalPattern": "、".join(str(item) for item in rhetorical[:3]) if rhetorical else None,
    }
