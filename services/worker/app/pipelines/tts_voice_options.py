from __future__ import annotations

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


def _vo_profile(structure: dict[str, Any]) -> dict[str, Any]:
    audio = structure.get("audio")
    if not isinstance(audio, dict):
        return {}
    profile = audio.get("voProfile")
    return dict(profile) if isinstance(profile, dict) else {}


def _pace_speech_rate(profile: dict[str, Any]) -> int | None:
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


def _energy_hint(profile: dict[str, Any]) -> str | None:
    energy = str(profile.get("energy") or "").strip().lower()
    return _ENERGY_HINTS.get(energy)


def _persona_hint(profile: dict[str, Any]) -> str | None:
    persona = str(profile.get("persona") or "").strip()
    if not persona:
        return None
    return f"以{persona}的口吻朗读"


def _compose_context_texts(*parts: str | None) -> str:
    ordered = [part.strip() for part in parts if isinstance(part, str) and part.strip()]
    return "；".join(ordered)


def build_tts_synthesis_options(
    *,
    structure: dict[str, Any],
    workbench_prefs: dict[str, Any],
    generation_id: str,
) -> dict[str, Any]:
    """Merge workbench TTS defaults with structure voProfile-derived prosody hints."""
    prefs = normalize_tts_preferences(workbench_prefs or DEFAULT_TTS_PREFERENCES)
    profile = _vo_profile(structure)

    vo_rate = _pace_speech_rate(profile)
    wpm_rate = _wpm_speech_rate(profile)
    speech_rate = int(prefs["speechRate"])
    if vo_rate is not None:
        speech_rate = vo_rate
    if wpm_rate is not None:
        speech_rate = max(-50, min(100, speech_rate + wpm_rate))

    context_texts = _compose_context_texts(
        _persona_hint(profile),
        _energy_hint(profile),
        str(prefs.get("contextTexts") or ""),
    )

    options: dict[str, Any] = {
        "generationId": generation_id,
        "resourceId": prefs["resourceId"],
        "speaker": prefs["speaker"],
        "modelVariant": prefs["modelVariant"],
        "speechRate": speech_rate,
        "loudnessRate": int(prefs["loudnessRate"]),
        "emotionScale": int(prefs["emotionScale"]),
        "contextTexts": context_texts,
        "explicitLanguage": prefs["explicitLanguage"],
        "format": prefs["format"],
        "sampleRate": int(prefs["sampleRate"]),
        "chunkCharLimit": int(prefs["chunkCharLimit"]),
    }
    emotion = prefs.get("emotion")
    if emotion:
        options["emotion"] = emotion
    return options
