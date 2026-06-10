from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from app.pipelines.master_narration import _normalize_compare, split_master_into_clauses, split_master_narration_by_duration
from app.pipelines.narration_alignment import wav_duration_sec
from app.pipelines.tts_voice_options import build_tts_synthesis_options, canonical_tts_options_key
from app.validation.schema_loader import validate_contract

NARRATION_PREVIEW_FILENAME = "narration-preview.json"
PREVIEW_WAV_REL = "preview/master.wav"


def narration_preview_path(generation_root: Path) -> Path:
    return generation_root / NARRATION_PREVIEW_FILENAME


def preview_wav_path(generation_root: Path) -> Path:
    return generation_root / PREVIEW_WAV_REL


def resolve_tts_options_key(
    *,
    structure: dict[str, Any] | None = None,
    workbench_prefs: dict[str, Any] | None = None,
    generation_id: str | None = None,
    draft: dict[str, Any] | None = None,
    tts_options_key: str | None = None,
) -> str | None:
    if tts_options_key:
        return tts_options_key
    if workbench_prefs is None:
        return None
    narration_vo_profile = (
        draft.get("narrationVoProfile") if isinstance(draft, dict) and isinstance(draft.get("narrationVoProfile"), dict) else None
    )
    options = build_tts_synthesis_options(
        structure=structure or {},
        workbench_prefs=workbench_prefs,
        generation_id=generation_id or "",
        narration_vo_profile=narration_vo_profile,
    )
    return canonical_tts_options_key(options)


def narration_content_hash(
    draft: dict[str, Any],
    *,
    structure: dict[str, Any] | None = None,
    workbench_prefs: dict[str, Any] | None = None,
    generation_id: str | None = None,
    tts_options_key: str | None = None,
) -> str:
    master = str(draft.get("masterNarration") or "").strip()
    vo_profile = draft.get("narrationVoProfile")
    resolved_tts_key = resolve_tts_options_key(
        structure=structure,
        workbench_prefs=workbench_prefs,
        generation_id=generation_id,
        draft=draft,
        tts_options_key=tts_options_key,
    )
    payload = {
        "masterNarration": master,
        "narrationVoProfile": vo_profile if isinstance(vo_profile, dict) else None,
        "ttsOptionsKey": resolved_tts_key,
    }
    digest = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return f"sha256:{digest}"


def narration_preview_is_current(
    generation_root: Path,
    draft: dict[str, Any],
    *,
    structure: dict[str, Any] | None = None,
    workbench_prefs: dict[str, Any] | None = None,
    generation_id: str | None = None,
) -> bool:
    preview = load_narration_preview(generation_root)
    if preview is None:
        return False
    scene_timing = preview.get("sceneTiming")
    if not isinstance(scene_timing, list) or not scene_timing:
        return False
    expected_hash = narration_content_hash(
        draft,
        structure=structure,
        workbench_prefs=workbench_prefs,
        generation_id=generation_id,
        tts_options_key=str(preview.get("ttsOptionsKey") or "") or None,
    )
    if preview.get("contentHash") != expected_hash:
        return False
    if preview.get("synthesisSkipped"):
        return True
    wav_path = preview_wav_path(generation_root)
    return wav_path.is_file() and wav_path.stat().st_size > 0


def load_narration_preview(generation_root: Path) -> dict[str, Any] | None:
    path = narration_preview_path(generation_root)
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def save_narration_preview(generation_root: Path, preview: dict[str, Any]) -> dict[str, Any]:
    validation = validate_contract("narration-preview", preview)
    if not validation.valid:
        raise ValueError(f"Invalid narration-preview payload: {validation.errors}")
    path = narration_preview_path(generation_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(preview, ensure_ascii=False, indent=2), encoding="utf-8")
    return preview


def clear_narration_preview(generation_root: Path) -> None:
    path = narration_preview_path(generation_root)
    if path.is_file():
        path.unlink()
    wav = preview_wav_path(generation_root)
    if wav.is_file():
        wav.unlink()


def ordered_structure_slots(structure: dict[str, Any]) -> list[dict[str, Any]]:
    slots = [
        dict(slot)
        for slot in structure.get("slots", [])
        if isinstance(slot, dict) and slot.get("id")
    ]
    return sorted(slots, key=lambda item: float(item.get("startSec", 0.0)))


def _pseudo_scenes_from_structure(structure: dict[str, Any]) -> list[dict[str, Any]]:
    scenes: list[dict[str, Any]] = []
    for slot in ordered_structure_slots(structure):
        start = float(slot.get("startSec", 0.0))
        end = float(slot.get("endSec", start))
        scenes.append(
            {
                "slotId": str(slot["id"]),
                "startSec": start,
                "endSec": max(start, end),
            }
        )
    return scenes


def allocate_scene_windows_proportional(
    structure: dict[str, Any],
    *,
    total_duration_sec: float,
) -> list[dict[str, Any]]:
    scenes = _pseudo_scenes_from_structure(structure)
    if not scenes:
        return []
    durations = [max(0.1, float(scene["endSec"]) - float(scene["startSec"])) for scene in scenes]
    total_weight = sum(durations) or float(len(scenes))
    windows: list[dict[str, Any]] = []
    cursor = 0.0
    for index, scene in enumerate(scenes):
        weight = durations[index] / total_weight
        if index == len(scenes) - 1:
            end_sec = round(total_duration_sec, 3)
        else:
            end_sec = round(cursor + total_duration_sec * weight, 3)
        windows.append(
            {
                "slotId": str(scene["slotId"]),
                "startSec": round(cursor, 3),
                "endSec": end_sec,
            }
        )
        cursor = end_sec
    return windows


def _clause_groups_for_slots(
    master_narration: str,
    structure: dict[str, Any],
) -> list[str]:
    pseudo_scenes = _pseudo_scenes_from_structure(structure)
    if not pseudo_scenes:
        return []
    return split_master_narration_by_duration(master_narration, pseudo_scenes)


def _whisper_segments_usable(segments: list[dict[str, Any]]) -> bool:
    if not segments:
        return False
    return any(str(item.get("text", "")).strip() for item in segments if isinstance(item, dict))


def allocate_scene_windows_from_whisper(
    *,
    master_narration: str,
    structure: dict[str, Any],
    whisper_segments: list[dict[str, Any]],
    total_duration_sec: float,
) -> tuple[list[dict[str, Any]], str, list[str]]:
    warnings: list[str] = []
    slots = ordered_structure_slots(structure)
    if not slots:
        return [], "proportional_fallback", ["no_structure_slots"]

    if not _whisper_segments_usable(whisper_segments):
        warnings.append("whisper_segments_empty")
        return (
            allocate_scene_windows_proportional(structure, total_duration_sec=total_duration_sec),
            "proportional_fallback",
            warnings,
        )

    clause_groups = _clause_groups_for_slots(master_narration, structure)
    normalized_segments = [
        {
            "startSec": float(item.get("startSec", 0.0)),
            "endSec": float(item.get("endSec", 0.0)),
            "text": _normalize_compare(str(item.get("text", ""))),
        }
        for item in whisper_segments
        if isinstance(item, dict) and str(item.get("text", "")).strip()
    ]
    if not normalized_segments:
        warnings.append("whisper_segments_unusable")
        return (
            allocate_scene_windows_proportional(structure, total_duration_sec=total_duration_sec),
            "proportional_fallback",
            warnings,
        )

    seg_cursor = 0
    windows: list[dict[str, Any]] = []
    low_confidence = False

    for index, slot in enumerate(slots):
        expected = _normalize_compare(clause_groups[index] if index < len(clause_groups) else "")
        if not expected:
            start_sec = windows[-1]["endSec"] if windows else 0.0
            if index == len(slots) - 1:
                end_sec = round(total_duration_sec, 3)
            else:
                proportional = allocate_scene_windows_proportional(
                    {"slots": [slot]},
                    total_duration_sec=max(0.5, total_duration_sec / len(slots)),
                )
                end_sec = round(start_sec + (proportional[0]["endSec"] - proportional[0]["startSec"]), 3)
            windows.append(
                {
                    "slotId": str(slot["id"]),
                    "startSec": round(start_sec, 3),
                    "endSec": end_sec,
                }
            )
            continue

        consumed = ""
        first_start: float | None = None
        last_end: float | None = None
        while seg_cursor < len(normalized_segments) and len(consumed) < len(expected):
            segment = normalized_segments[seg_cursor]
            if first_start is None:
                first_start = segment["startSec"]
            last_end = segment["endSec"]
            consumed += segment["text"]
            seg_cursor += 1

        if first_start is None or last_end is None or len(consumed) < max(1, int(len(expected) * 0.5)):
            low_confidence = True
            break

        windows.append(
            {
                "slotId": str(slot["id"]),
                "startSec": round(first_start, 3),
                "endSec": round(last_end, 3),
            }
        )

    if low_confidence or len(windows) != len(slots):
        warnings.append("whisper_match_low_confidence")
        return (
            allocate_scene_windows_proportional(structure, total_duration_sec=total_duration_sec),
            "proportional_fallback",
            warnings,
        )

    for index in range(1, len(windows)):
        if windows[index]["startSec"] < windows[index - 1]["endSec"]:
            windows[index]["startSec"] = windows[index - 1]["endSec"]

    windows[-1]["endSec"] = round(total_duration_sec, 3)
    for index in range(len(windows) - 1):
        windows[index]["endSec"] = min(windows[index]["endSec"], windows[index + 1]["startSec"])

    return windows, "whisper", warnings


def apply_narration_timing_to_storyboard(
    storyboard: list[dict[str, Any]],
    scene_timing: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    timing_by_slot = {
        str(item["slotId"]): item
        for item in scene_timing
        if isinstance(item, dict) and item.get("slotId")
    }
    updated: list[dict[str, Any]] = []
    for scene in storyboard:
        if not isinstance(scene, dict):
            continue
        item = dict(scene)
        timing = timing_by_slot.get(str(item.get("slotId", "")))
        if timing is not None:
            item["startSec"] = round(float(timing.get("startSec", 0.0)), 3)
            item["endSec"] = round(float(timing.get("endSec", item["startSec"])), 3)
        updated.append(item)
    return updated


def estimate_narration_duration_sec(
    draft: dict[str, Any],
    structure: dict[str, Any],
) -> float:
    target = float(
        draft.get("durationTargetSec")
        or (structure.get("metadata") or {}).get("durationSec")
        or 30.0
    )
    master = str(draft.get("masterNarration") or "").strip()
    if not master:
        return max(1.0, target)
    # Rough spoken Chinese pacing (~4 chars/sec) with floor at structure target.
    char_estimate = max(1.0, len(master) / 4.0)
    return round(max(target, char_estimate), 3)


def build_structure_estimate_preview(
    *,
    generation_root: Path,
    draft: dict[str, Any],
    structure: dict[str, Any],
    workbench_prefs: dict[str, Any] | None = None,
    generation_id: str | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    duration_sec = estimate_narration_duration_sec(draft, structure)
    scene_timing = allocate_scene_windows_proportional(structure, total_duration_sec=duration_sec)
    tts_key = resolve_tts_options_key(
        structure=structure,
        workbench_prefs=workbench_prefs,
        generation_id=generation_id,
        draft=draft,
    )
    preview = {
        "contentHash": narration_content_hash(
            draft,
            structure=structure,
            workbench_prefs=workbench_prefs,
            generation_id=generation_id,
            tts_options_key=tts_key,
        ),
        "durationSec": duration_sec,
        "wavUri": PREVIEW_WAV_REL,
        "alignmentMethod": "structure_estimate",
        "sceneTiming": scene_timing,
        "warnings": list(warnings or []),
        "synthesisSkipped": True,
    }
    if tts_key:
        preview["ttsOptionsKey"] = tts_key
    return save_narration_preview(generation_root, preview)


def build_narration_preview(
    *,
    generation_root: Path,
    draft: dict[str, Any],
    structure: dict[str, Any],
    whisper_segments: list[dict[str, Any]],
    wav_uri: str,
    duration_sec: float | None = None,
    workbench_prefs: dict[str, Any] | None = None,
    generation_id: str | None = None,
) -> dict[str, Any]:
    wav_path = generation_root / wav_uri
    resolved_duration = duration_sec
    if resolved_duration is None and wav_path.is_file():
        resolved_duration = wav_duration_sec(wav_path)
    if resolved_duration is None or resolved_duration <= 0:
        raise ValueError("narration_preview_duration_unavailable")

    scene_timing, alignment_method, warnings = allocate_scene_windows_from_whisper(
        master_narration=str(draft.get("masterNarration") or ""),
        structure=structure,
        whisper_segments=whisper_segments,
        total_duration_sec=float(resolved_duration),
    )
    tts_key = resolve_tts_options_key(
        structure=structure,
        workbench_prefs=workbench_prefs,
        generation_id=generation_id,
        draft=draft,
    )
    preview: dict[str, Any] = {
        "contentHash": narration_content_hash(
            draft,
            structure=structure,
            workbench_prefs=workbench_prefs,
            generation_id=generation_id,
            tts_options_key=tts_key,
        ),
        "durationSec": round(float(resolved_duration), 3),
        "wavUri": wav_uri,
        "alignmentMethod": alignment_method,
        "sceneTiming": scene_timing,
        "warnings": warnings,
        "synthesisSkipped": False,
    }
    if tts_key:
        preview["ttsOptionsKey"] = tts_key
    return preview


def transcribe_preview_wav(
    wav_path: Path,
    *,
    whisper_tool: Any | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    from app.tools.whisper_tool import WHISPER_SOFT_FAIL_CODES, WhisperTool

    warnings: list[str] = []
    tool = whisper_tool or WhisperTool()
    result = tool.transcribe(wav_path)
    if not isinstance(result, dict):
        return [], ["whisper_invalid_response"]
    code = str(result.get("code", ""))
    if code in WHISPER_SOFT_FAIL_CODES:
        warnings.append(code)
        return [], warnings
    segments = result.get("segments")
    if not isinstance(segments, list):
        warnings.append("whisper_missing_segments")
        return [], warnings
    normalized = [item for item in segments if isinstance(item, dict)]
    return normalized, warnings


def ensure_narration_preview(
    *,
    generation_root: Path,
    draft: dict[str, Any],
    structure: dict[str, Any],
    synthesize_preview: Callable[[], Path],
    transcribe_wav: Callable[[Path], tuple[list[dict[str, Any]], list[str]]],
    workbench_prefs: dict[str, Any] | None = None,
    generation_id: str | None = None,
) -> dict[str, Any]:
    if narration_preview_is_current(
        generation_root,
        draft,
        structure=structure,
        workbench_prefs=workbench_prefs,
        generation_id=generation_id,
    ):
        existing = load_narration_preview(generation_root)
        assert existing is not None
        return existing

    output_path = synthesize_preview()
    segments, transcribe_warnings = transcribe_wav(output_path)
    duration = wav_duration_sec(output_path)
    preview = build_narration_preview(
        generation_root=generation_root,
        draft=draft,
        structure=structure,
        whisper_segments=segments,
        wav_uri=PREVIEW_WAV_REL,
        duration_sec=duration,
        workbench_prefs=workbench_prefs,
        generation_id=generation_id,
    )
    preview["warnings"] = list(dict.fromkeys([*preview.get("warnings", []), *transcribe_warnings]))
    save_narration_preview(generation_root, preview)
    return preview


def unmark_checkpoint_stage(generation_root: Path, stage: str) -> None:
    checkpoint_path = generation_root / "checkpoint.json"
    if not checkpoint_path.is_file():
        return
    payload = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return
    completed = payload.get("completedStages")
    if isinstance(completed, list) and stage in completed:
        payload["completedStages"] = [item for item in completed if item != stage]
        checkpoint_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def narration_timing_payload(preview: dict[str, Any]) -> dict[str, Any]:
    return {
        "durationSec": float(preview.get("durationSec", 0.0)),
        "sceneTiming": list(preview.get("sceneTiming") or []),
        "alignmentMethod": str(preview.get("alignmentMethod") or ""),
        "warnings": list(preview.get("warnings") or []),
    }


def storyboard_scripts_match_master(storyboard: list[dict[str, Any]], master_narration: str) -> bool:
    master_norm = _normalize_compare(master_narration)
    if not master_norm:
        return False
    parts = [
        _normalize_compare(str(scene.get("script") or ""))
        for scene in sorted(
            [s for s in storyboard if isinstance(s, dict)],
            key=lambda item: float(item.get("startSec", 0.0)),
        )
        if str(scene.get("script") or "").strip()
    ]
    combined = "".join(parts)
    return combined == master_norm


def reconcile_storyboard_to_segment_durations(
    storyboard: list[dict[str, Any]],
    *,
    segment_durations: list[tuple[str, float]],
) -> list[dict[str, Any]]:
    """Adjust scene endSec/startSec from per-scene TTS segment wav durations."""
    if not storyboard or not segment_durations:
        return storyboard
    duration_by_slot = {slot_id: duration for slot_id, duration in segment_durations}
    scenes = sorted(
        [dict(scene) for scene in storyboard if isinstance(scene, dict)],
        key=lambda item: float(item.get("startSec", 0.0)),
    )
    cursor = 0.0
    updated: list[dict[str, Any]] = []
    for scene in scenes:
        slot_id = str(scene.get("slotId", ""))
        duration = duration_by_slot.get(slot_id)
        if duration is None or duration <= 0:
            start = float(scene.get("startSec", cursor))
            end = float(scene.get("endSec", start))
            duration = max(0.1, end - start)
        scene["startSec"] = round(cursor, 3)
        scene["endSec"] = round(cursor + duration, 3)
        updated.append(scene)
        cursor = float(scene["endSec"])
    timing_by_slot = {str(scene["slotId"]): scene for scene in updated}
    return [
        timing_by_slot.get(str(scene.get("slotId", "")), scene)
        if isinstance(scene, dict)
        else scene
        for scene in storyboard
    ]
