from __future__ import annotations

from typing import Any


def _segment_vo_hints(video_structure: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(video_structure, dict):
        return []
    narrative = video_structure.get("narrative")
    if not isinstance(narrative, dict):
        return []
    hints: list[dict[str, Any]] = []
    for segment in narrative.get("segments") or []:
        if not isinstance(segment, dict):
            continue
        hint: dict[str, Any] = {
            "role": segment.get("role"),
            "emotionTone": segment.get("emotionTone"),
        }
        vo_style = segment.get("voStyle")
        if isinstance(vo_style, dict):
            hint["voStyle"] = vo_style
        visual_spec = segment.get("visualSpec")
        if isinstance(visual_spec, dict):
            hint["visualSpec"] = {
                key: visual_spec.get(key)
                for key in ("shotScale", "cameraMotion", "colorMood", "onScreenText")
                if visual_spec.get(key) is not None
            }
        if any(hint.get(key) for key in ("emotionTone", "voStyle", "visualSpec")):
            hints.append(hint)
    return hints


def structure_generation_hints(video_structure: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(video_structure, dict):
        return {}
    hints: dict[str, Any] = {}
    vo_hints = _segment_vo_hints(video_structure)
    if vo_hints:
        hints["sampleVoHints"] = vo_hints

    context = video_structure.get("context")
    if isinstance(context, dict):
        context_hint: dict[str, Any] = {}
        for key in ("contentCategory", "primaryIntent", "successHypothesis"):
            if context.get(key):
                context_hint[key] = context.get(key)
        if context_hint:
            hints["sampleContextHints"] = context_hint

    verbal = video_structure.get("verbal")
    if isinstance(verbal, dict):
        verbal_hint: dict[str, Any] = {}
        if verbal.get("hookTemplate"):
            verbal_hint["hookTemplate"] = verbal.get("hookTemplate")
        if verbal.get("ctaMechanism"):
            verbal_hint["ctaMechanism"] = verbal.get("ctaMechanism")
        if verbal_hint:
            hints["sampleVerbalHints"] = verbal_hint

    rhythm = video_structure.get("rhythm")
    if isinstance(rhythm, dict):
        rhythm_hint: dict[str, Any] = {}
        if rhythm.get("tempo"):
            rhythm_hint["tempo"] = rhythm.get("tempo")
        beat_points = rhythm.get("beatPoints")
        if isinstance(beat_points, list) and beat_points:
            rhythm_hint["beatPointCount"] = len(beat_points)
        if rhythm_hint:
            hints["sampleRhythmHints"] = rhythm_hint

    packaging = video_structure.get("packaging")
    visual = video_structure.get("visual")
    if isinstance(visual, dict) and isinstance(visual.get("packagingSpec"), dict):
        spec = visual["packagingSpec"]
        packaging_hint: dict[str, Any] = {}
        if spec.get("visualDensity"):
            packaging_hint["visualDensity"] = spec.get("visualDensity")
        if spec.get("summary"):
            packaging_hint["summary"] = spec.get("summary")
        if packaging_hint:
            hints["samplePackagingHints"] = packaging_hint
    elif isinstance(packaging, dict):
        packaging_hint: dict[str, Any] = {}
        if packaging.get("visualDensity"):
            packaging_hint["visualDensity"] = packaging.get("visualDensity")
        title_cards = packaging.get("titleCards")
        if isinstance(title_cards, list) and title_cards:
            packaging_hint["titleCardCount"] = len(title_cards)
        if packaging_hint:
            hints["samplePackagingHints"] = packaging_hint

    if isinstance(visual, dict) and isinstance(visual.get("cutRateProfile"), dict):
        hints["sampleCutRateProfile"] = visual["cutRateProfile"]

    transfer = video_structure.get("transfer")
    if isinstance(transfer, dict):
        if transfer.get("differentiationLever"):
            hints["sampleDifferentiationLever"] = transfer.get("differentiationLever")
        triggers = transfer.get("emotionTriggers")
        if isinstance(triggers, list) and triggers:
            hints["sampleEmotionTriggers"] = triggers[:5]

    return hints
