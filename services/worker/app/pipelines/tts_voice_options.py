from __future__ import annotations

from collections.abc import Callable
from typing import Any

try:
    from model_gateway.tts_preferences import DEFAULT_TTS_PREFERENCES, normalize_tts_preferences
except ImportError:  # pragma: no cover
    DEFAULT_TTS_PREFERENCES = {}
    normalize_tts_preferences = lambda raw: dict(raw or {})  # type: ignore[assignment, misc]

_PACE_TO_RATE = {
    "slow": -25,
    "medium": 0,
    "fast": 30,
}

_ENERGY_HINTS = {
    "low": "语速平稳、克制，情绪收敛",
    "medium": "自然口播，语气亲切",
    "high": "更有感染力，语调起伏明显",
}

_VALID_PACE = frozenset(_PACE_TO_RATE)
_VALID_ENERGY = frozenset(_ENERGY_HINTS)


def _vo_profile(structure: dict[str, Any]) -> dict[str, Any]:
    audio = structure.get("audio")
    if not isinstance(audio, dict):
        return {}
    profile = audio.get("voProfile")
    return dict(profile) if isinstance(profile, dict) else {}


def normalize_vo_directive(raw: Any) -> tuple[dict[str, Any] | None, list[str]]:
    """Validate and coerce LLM/script vo directive fields."""
    warnings: list[str] = []
    if not isinstance(raw, dict) or not raw:
        return None, warnings

    normalized: dict[str, Any] = {}
    pace = str(raw.get("pace") or "").strip().lower()
    if pace:
        if pace in _VALID_PACE:
            normalized["pace"] = pace
        else:
            warnings.append(f"invalid_vo_directive_pace:{pace}")

    energy = str(raw.get("energy") or "").strip().lower()
    if energy:
        if energy in _VALID_ENERGY:
            normalized["energy"] = energy
        else:
            warnings.append(f"invalid_vo_directive_energy:{energy}")

    persona = str(raw.get("persona") or "").strip()
    if persona:
        normalized["persona"] = persona[:80]

    context_hint = str(raw.get("contextHint") or "").strip()
    if context_hint:
        normalized["contextHint"] = context_hint[:200]

    emotion = str(raw.get("emotion") or "").strip()
    if emotion:
        normalized["emotion"] = emotion[:32]

    for int_key, lo, hi in (
        ("speechRate", -50, 100),
        ("loudnessRate", -50, 100),
        ("emotionScale", 1, 5),
    ):
        if raw.get(int_key) is None:
            continue
        try:
            value = int(raw[int_key])
        except (TypeError, ValueError):
            warnings.append(f"invalid_vo_directive_{int_key}")
            continue
        if lo <= value <= hi:
            normalized[int_key] = value
        else:
            warnings.append(f"out_of_range_vo_directive_{int_key}:{value}")

    if not normalized:
        return None, warnings
    return normalized, warnings


def report_vo_directive_warnings(
    warnings: list[str],
    *,
    emit_event: Callable[..., Any] | None = None,
    emit_progress: Callable[[str, str], None] | None = None,
) -> None:
    """Surface coerced/invalid LLM vo directive fields to task progress or SSE."""
    if not warnings:
        return
    message = "; ".join(dict.fromkeys(warnings))
    if emit_progress is not None:
        emit_progress("vo_directive_normalized", message)
    elif emit_event is not None:
        emit_event(stage="vo_directive_normalized", progress=0, message=message)


def _merge_vo_layers(*layers: dict[str, Any] | None) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for layer in layers:
        if not isinstance(layer, dict):
            continue
        for key, value in layer.items():
            if value is None:
                continue
            if isinstance(value, str) and not value.strip():
                continue
            merged[key] = value
    return merged


def _pace_speech_rate(profile: dict[str, Any]) -> int | None:
    if profile.get("speechRate") is not None:
        try:
            return int(profile["speechRate"])
        except (TypeError, ValueError):
            pass
    pace = str(profile.get("pace") or "").strip().lower()
    if pace in _PACE_TO_RATE:
        return _PACE_TO_RATE[pace]
    return None


def _wpm_speech_rate(profile: dict[str, Any]) -> int | None:
    raw = profile.get("wordsPerMinute")
    try:
        wpm = float(raw)
    except (TypeError, ValueError):
        return None
    delta = int(round((wpm - 160.0) / 4.0))
    return max(-15, min(15, delta))


def _energy_hint(profile: dict[str, Any] | None) -> str | None:
    if not profile:
        return None
    energy = str(profile.get("energy") or "").strip().lower()
    return _ENERGY_HINTS.get(energy)


def _persona_hint(profile: dict[str, Any] | None) -> str | None:
    if not profile:
        return None
    persona = str(profile.get("persona") or "").strip()
    if not persona:
        return None
    return f"以{persona}的口吻朗读"


def _context_hint(profile: dict[str, Any] | None) -> str | None:
    if not profile:
        return None
    hint = str(profile.get("contextHint") or "").strip()
    return hint or None


def _compose_context_texts(*parts: str | None) -> str:
    ordered = [part.strip() for part in parts if isinstance(part, str) and part.strip()]
    return "；".join(ordered)


def build_tts_synthesis_options(
    *,
    structure: dict[str, Any],
    workbench_prefs: dict[str, Any],
    generation_id: str,
    narration_vo_profile: dict[str, Any] | None = None,
    scene_vo_directive: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Merge workbench, sample voProfile, and LLM script vo directives for TTS."""
    prefs = normalize_tts_preferences(workbench_prefs or DEFAULT_TTS_PREFERENCES)
    structure_profile = _vo_profile(structure)
    narration_layer, _ = normalize_vo_directive(narration_vo_profile)
    scene_layer, _ = normalize_vo_directive(scene_vo_directive)
    merged = _merge_vo_layers(structure_profile, narration_layer, scene_layer)

    vo_rate = _pace_speech_rate(merged)
    wpm_rate = _wpm_speech_rate(structure_profile)
    speech_rate = int(prefs["speechRate"])
    if vo_rate is not None:
        speech_rate = vo_rate
    elif wpm_rate is not None:
        speech_rate = max(-50, min(100, speech_rate + wpm_rate))

    loudness_rate = int(prefs["loudnessRate"])
    if merged.get("loudnessRate") is not None:
        loudness_rate = int(merged["loudnessRate"])

    emotion_scale = int(prefs["emotionScale"])
    if merged.get("emotionScale") is not None:
        emotion_scale = int(merged["emotionScale"])

    # contextTexts: workbench baseline first (lowest), then sample → narration → scene hints,
    # then merged persona/energy (highest semantic weight in the joined string).
    context_texts = _compose_context_texts(
        str(prefs.get("contextTexts") or ""),
        _context_hint(structure_profile),
        _context_hint(narration_layer),
        _context_hint(scene_layer),
        _persona_hint(merged),
        _energy_hint(merged),
    )

    options: dict[str, Any] = {
        "generationId": generation_id,
        "resourceId": prefs["resourceId"],
        "speaker": prefs["speaker"],
        "modelVariant": prefs["modelVariant"],
        "speechRate": speech_rate,
        "loudnessRate": loudness_rate,
        "emotionScale": emotion_scale,
        "contextTexts": context_texts,
        "explicitLanguage": prefs["explicitLanguage"],
        "format": prefs["format"],
        "sampleRate": int(prefs["sampleRate"]),
        "chunkCharLimit": int(prefs["chunkCharLimit"]),
    }
    emotion = merged.get("emotion") or prefs.get("emotion")
    if emotion:
        options["emotion"] = str(emotion)
    return options


def canonical_tts_options_key(options: dict[str, Any]) -> str:
    """Stable comparison key for per-scene TTS option equality (ignores generationId)."""
    import json

    payload = {key: value for key, value in options.items() if key != "generationId"}
    return json.dumps(payload, sort_keys=True, ensure_ascii=False)
