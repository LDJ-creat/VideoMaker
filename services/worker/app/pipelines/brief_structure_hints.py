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
    if isinstance(packaging, dict):
        packaging_hint: dict[str, Any] = {}
        if packaging.get("visualDensity"):
            packaging_hint["visualDensity"] = packaging.get("visualDensity")
        title_cards = packaging.get("titleCards")
        if isinstance(title_cards, list) and title_cards:
            packaging_hint["titleCardCount"] = len(title_cards)
        if packaging_hint:
            hints["samplePackagingHints"] = packaging_hint

    return hints
