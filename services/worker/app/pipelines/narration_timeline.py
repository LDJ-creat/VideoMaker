from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

from app.pipelines.narration_alignment import wav_duration_sec
from app.pipelines.tts_mode import (
    MASTER_TTS_SLOT_ID,
    MASTER_TTS_WAV_NAME,
    VO_MASTER_CLIP_ID,
    is_global_tts_mode,
    resolve_tts_mode,
)

NarrationTimelineMode = Literal["hold_tail", "ripple_overflow", "scale_to_target", "global_ripple"]


def resolve_narration_timeline_mode() -> NarrationTimelineMode:
    env = os.getenv("VIDEOMAKER_NARRATION_TIMELINE_MODE", "hold_tail").strip().lower()
    if env in {"hold_tail", "ripple_overflow", "scale_to_target", "global_ripple"}:
        return env  # type: ignore[return-value]
    return "hold_tail"


def _voiceover_track(tracks: list[Any]) -> dict[str, Any] | None:
    for track in tracks:
        if isinstance(track, dict) and track.get("type") == "voiceover":
            return track
    return None


def _resolve_wav_path(source_ref: str, render_root: Path | None) -> Path | None:
    if render_root is not None and source_ref:
        candidate = render_root / source_ref
        if candidate.is_file():
            return candidate
    if source_ref:
        path = Path(source_ref)
        if path.is_file():
            return path
    return None


def _wav_duration_for_slot(
    slot_id: str,
    *,
    render_root: Path | None,
    vo_clips: dict[str, dict[str, Any]],
) -> float | None:
    if slot_id == MASTER_TTS_SLOT_ID:
        vo_clip = vo_clips.get(VO_MASTER_CLIP_ID)
        if vo_clip is not None:
            source_ref = str(vo_clip.get("sourceRef", ""))
            wav_path = _resolve_wav_path(source_ref, render_root)
            if wav_path is not None:
                return wav_duration_sec(wav_path)
        if render_root is not None:
            candidate = render_root / "materials" / MASTER_TTS_WAV_NAME
            if candidate.is_file():
                return wav_duration_sec(candidate)
        return None

    vo_clip = vo_clips.get(f"vo-{slot_id}")
    if vo_clip is not None:
        source_ref = str(vo_clip.get("sourceRef", ""))
        wav_path = _resolve_wav_path(source_ref, render_root)
        if wav_path is not None:
            return wav_duration_sec(wav_path)
    if render_root is not None:
        candidate = render_root / "materials" / f"{slot_id}.wav"
        if candidate.is_file():
            return wav_duration_sec(candidate)
    return None


def narration_end_sec(
    plan: dict[str, Any],
    *,
    render_root: Path | None = None,
) -> float | None:
    timeline = plan.get("timeline", {})
    tracks = timeline.get("tracks", [])
    if not isinstance(tracks, list):
        return None

    tts_mode = str(plan.get("ttsMode") or resolve_tts_mode(plan))
    vo_track = _voiceover_track(tracks)
    vo_clips: dict[str, dict[str, Any]] = {}
    if vo_track is not None:
        for clip in vo_track.get("clips", []):
            if isinstance(clip, dict):
                vo_clips[str(clip.get("id", ""))] = clip

    if is_global_tts_mode(tts_mode):
        duration = _wav_duration_for_slot(
            MASTER_TTS_SLOT_ID,
            render_root=render_root,
            vo_clips=vo_clips,
        )
        if duration is not None and duration > 0:
            return duration
        master_clip = vo_clips.get(VO_MASTER_CLIP_ID)
        if master_clip is not None:
            return float(master_clip.get("endSec", 0.0))
        return None

    storyboard = plan.get("storyboard", [])
    if not isinstance(storyboard, list):
        return None

    max_end = 0.0
    found = False
    for scene in storyboard:
        if not isinstance(scene, dict):
            continue
        slot_id = str(scene.get("slotId", ""))
        if not slot_id:
            continue
        start_sec = float(scene.get("startSec", 0.0))
        wav_duration = _wav_duration_for_slot(
            slot_id,
            render_root=render_root,
            vo_clips=vo_clips,
        )
        if wav_duration is not None and wav_duration > 0:
            max_end = max(max_end, start_sec + wav_duration)
            found = True
            continue
        vo_clip = vo_clips.get(f"vo-{slot_id}")
        if vo_clip is not None:
            max_end = max(max_end, float(vo_clip.get("endSec", start_sec)))
            found = True
    return max_end if found else None


def _planned_duration_sec(plan: dict[str, Any]) -> float:
    timeline = plan.get("timeline", {})
    if isinstance(timeline, dict) and timeline.get("durationSec"):
        return float(timeline["durationSec"])
    storyboard = plan.get("storyboard", [])
    if isinstance(storyboard, list) and storyboard:
        return max(float(scene.get("endSec", 0.0)) for scene in storyboard if isinstance(scene, dict))
    return 0.0


def _sorted_storyboard(storyboard: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(storyboard, key=lambda scene: float(scene.get("startSec", 0.0)))


def _ripple_scene_timing(
    storyboard: list[dict[str, Any]],
    *,
    render_root: Path | None,
    vo_clips: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    scenes = [dict(scene) for scene in _sorted_storyboard(storyboard)]
    offset = 0.0
    rippled: list[dict[str, Any]] = []
    for scene in scenes:
        start_sec = float(scene.get("startSec", 0.0)) + offset
        end_sec = float(scene.get("endSec", start_sec)) + offset
        slot_id = str(scene.get("slotId", ""))
        scene_duration = max(0.0, end_sec - start_sec)
        wav_duration = _wav_duration_for_slot(
            slot_id,
            render_root=render_root,
            vo_clips=vo_clips,
        )
        overflow = 0.0
        if wav_duration is not None and wav_duration > scene_duration + 0.01:
            overflow = wav_duration - scene_duration
        scene["startSec"] = round(start_sec, 3)
        scene["endSec"] = round(end_sec + overflow, 3)
        rippled.append(scene)
        offset += overflow
    return rippled


def _apply_storyboard_to_timeline_clips(
    timeline: dict[str, Any],
    storyboard: list[dict[str, Any]],
) -> None:
    timing_by_slot = {
        str(scene.get("slotId", "")): (
            float(scene.get("startSec", 0.0)),
            float(scene.get("endSec", 0.0)),
        )
        for scene in storyboard
        if isinstance(scene, dict) and scene.get("slotId")
    }
    tracks = timeline.get("tracks", [])
    if not isinstance(tracks, list):
        return

    sorted_scenes = _sorted_storyboard([s for s in storyboard if isinstance(s, dict)])
    for current, nxt in zip(sorted_scenes, sorted_scenes[1:]):
        transition_id = f"transition-{current.get('id')}-to-{nxt.get('id')}"
        start = float(current["endSec"])
        end = min(float(nxt["startSec"]) + 0.18, max(float(nxt["startSec"]), start + 0.18))
        for track in tracks:
            if not isinstance(track, dict) or track.get("type") != "transition":
                continue
            for clip in track.get("clips", []):
                if isinstance(clip, dict) and str(clip.get("id", "")) == transition_id:
                    clip["startSec"] = round(start, 3)
                    clip["endSec"] = round(end, 3)

    for track in tracks:
        if not isinstance(track, dict):
            continue
        track_type = str(track.get("type", ""))
        if track_type not in {"video", "image"}:
            continue
        for clip in track.get("clips", []):
            if not isinstance(clip, dict):
                continue
            clip_id = str(clip.get("id", ""))
            if not clip_id.startswith("clip-"):
                continue
            slot_id = clip_id.removeprefix("clip-")
            timing = timing_by_slot.get(slot_id)
            if timing is None:
                continue
            clip["startSec"] = round(timing[0], 3)
            clip["endSec"] = round(timing[1], 3)


def _refresh_voiceover_clips(
    timeline: dict[str, Any],
    storyboard: list[dict[str, Any]],
    *,
    render_root: Path | None,
    tts_mode: str,
) -> None:
    tracks = timeline.get("tracks", [])
    if not isinstance(tracks, list):
        return
    vo_track = _voiceover_track(tracks)
    if vo_track is None:
        return

    timing_by_slot = {
        str(scene.get("slotId", "")): (
            float(scene.get("startSec", 0.0)),
            float(scene.get("endSec", 0.0)),
        )
        for scene in storyboard
        if isinstance(scene, dict) and scene.get("slotId")
    }

    for clip in vo_track.get("clips", []):
        if not isinstance(clip, dict):
            continue
        clip_id = str(clip.get("id", ""))
        if clip_id == VO_MASTER_CLIP_ID:
            source_ref = str(clip.get("sourceRef", ""))
            wav_path = _resolve_wav_path(source_ref, render_root)
            duration = wav_duration_sec(wav_path) if wav_path else None
            if duration and duration > 0:
                clip["startSec"] = 0.0
                clip["endSec"] = round(duration, 3)
            continue

        if not clip_id.startswith("vo-"):
            continue
        slot_id = clip_id.removeprefix("vo-")
        start_sec, storyboard_end = timing_by_slot.get(slot_id, (float(clip.get("startSec", 0.0)), 0.0))
        source_ref = str(clip.get("sourceRef", ""))
        wav_path = _resolve_wav_path(source_ref, render_root)
        duration = wav_duration_sec(wav_path) if wav_path else None
        clip["startSec"] = round(start_sec, 3)
        if duration and duration > 0:
            mode = resolve_narration_timeline_mode()
            if mode == "ripple_overflow" and not is_global_tts_mode(tts_mode):
                clip["endSec"] = round(start_sec + duration, 3)
            else:
                clip["endSec"] = round(min(storyboard_end, start_sec + duration), 3)
        else:
            clip["endSec"] = round(storyboard_end, 3)


def _global_proportional_scale(
    plan: dict[str, Any],
    narration_end: float,
) -> None:
    storyboard = plan.get("storyboard", [])
    timeline = plan.get("timeline", {})
    if not isinstance(storyboard, list) or not isinstance(timeline, dict):
        return

    planned = _planned_duration_sec(plan)
    if planned <= 0 or narration_end <= 0:
        _hold_tail(plan, narration_end)
        return

    ratio = narration_end / planned
    if abs(ratio - 1.0) <= 0.01:
        plan["timeline"]["durationSec"] = round(max(planned, narration_end), 3)
        return

    scaled: list[dict[str, Any]] = []
    for scene in _sorted_storyboard([s for s in storyboard if isinstance(s, dict)]):
        item = dict(scene)
        item["startSec"] = round(float(item.get("startSec", 0.0)) * ratio, 3)
        item["endSec"] = round(float(item.get("endSec", 0.0)) * ratio, 3)
        scaled.append(item)

    if scaled:
        scaled[-1]["endSec"] = round(narration_end, 3)
        for index in range(1, len(scaled)):
            if scaled[index]["startSec"] < scaled[index - 1]["endSec"]:
                scaled[index]["startSec"] = scaled[index - 1]["endSec"]

    timing_by_id = {str(scene.get("id", "")): scene for scene in scaled}
    updated = []
    for scene in storyboard:
        if not isinstance(scene, dict):
            updated.append(scene)
            continue
        merged = dict(scene)
        override = timing_by_id.get(str(scene.get("id", "")))
        if override is not None:
            merged["startSec"] = override["startSec"]
            merged["endSec"] = override["endSec"]
        updated.append(merged)

    plan["storyboard"] = updated
    plan["timeline"]["durationSec"] = round(narration_end, 3)
    _apply_storyboard_to_timeline_clips(plan["timeline"], updated)


def _should_use_global_ripple(
    *,
    resolved_mode: NarrationTimelineMode,
    narration_end: float,
    preview_duration_sec: float | None,
) -> bool:
    if resolved_mode == "global_ripple":
        return True
    if preview_duration_sec is None or preview_duration_sec <= 0 or narration_end <= 0:
        return False
    deviation = abs(narration_end - preview_duration_sec) / preview_duration_sec
    return deviation > 0.03


def _hold_tail(
    plan: dict[str, Any],
    narration_end: float,
) -> None:
    storyboard = plan.get("storyboard", [])
    timeline = plan.get("timeline", {})
    if not isinstance(storyboard, list) or not isinstance(timeline, dict):
        return

    planned = _planned_duration_sec(plan)
    if planned > narration_end * 1.25:
        planned = narration_end
    new_duration = max(planned, narration_end)
    if new_duration <= planned + 0.01 and planned >= narration_end - 0.01:
        plan["timeline"]["durationSec"] = round(max(planned, narration_end), 3)
        return

    scenes = _sorted_storyboard([s for s in storyboard if isinstance(s, dict)])
    if not scenes:
        return

    last_scene = dict(scenes[-1])
    last_scene["endSec"] = round(new_duration, 3)
    updated = [dict(scene) for scene in storyboard if isinstance(scene, dict)]
    last_scene_id = str(last_scene.get("id", ""))
    for index, scene in enumerate(updated):
        if str(scene.get("id", "")) == last_scene_id:
            updated[index] = last_scene
            break

    plan["storyboard"] = updated
    plan["timeline"]["durationSec"] = round(new_duration, 3)
    _apply_storyboard_to_timeline_clips(plan["timeline"], updated)


def sync_timeline_to_narration(
    plan: dict[str, Any],
    *,
    render_root: Path | None = None,
    mode: NarrationTimelineMode | None = None,
    preview_duration_sec: float | None = None,
) -> dict[str, Any]:
    """Adjust storyboard/timeline duration to fit synthesized narration."""
    resolved_mode = mode or resolve_narration_timeline_mode()
    tts_mode = str(plan.get("ttsMode") or resolve_tts_mode(plan))
    narration_end = narration_end_sec(plan, render_root=render_root)
    if narration_end is None or narration_end <= 0:
        return plan

    plan["narrationDurationSec"] = round(narration_end, 3)
    timeline = plan.get("timeline", {})
    tracks = timeline.get("tracks", []) if isinstance(timeline, dict) else []
    vo_clips: dict[str, dict[str, Any]] = {}
    if isinstance(tracks, list):
        vo_track = _voiceover_track(tracks)
        if vo_track is not None:
            for clip in vo_track.get("clips", []):
                if isinstance(clip, dict):
                    vo_clips[str(clip.get("id", ""))] = clip

    if resolved_mode == "ripple_overflow" and not is_global_tts_mode(tts_mode):
        storyboard = plan.get("storyboard", [])
        if isinstance(storyboard, list):
            rippled = _ripple_scene_timing(
                [s for s in storyboard if isinstance(s, dict)],
                render_root=render_root,
                vo_clips=vo_clips,
            )
            plan["storyboard"] = rippled
            if isinstance(timeline, dict):
                _apply_storyboard_to_timeline_clips(timeline, rippled)
                plan["timeline"]["durationSec"] = round(
                    max(float(scene.get("endSec", 0.0)) for scene in rippled),
                    3,
                )
    elif is_global_tts_mode(tts_mode) and _should_use_global_ripple(
        resolved_mode=resolved_mode,
        narration_end=narration_end,
        preview_duration_sec=(
            preview_duration_sec
            if preview_duration_sec is not None
            else (
                float(plan["narrationPreviewDurationSec"])
                if plan.get("narrationPreviewDurationSec") is not None
                else None
            )
        ),
    ):
        _global_proportional_scale(plan, narration_end)
    elif resolved_mode == "hold_tail" or is_global_tts_mode(tts_mode):
        _hold_tail(plan, narration_end)
    elif resolved_mode == "scale_to_target":
        _hold_tail(plan, narration_end)

    if isinstance(plan.get("timeline"), dict):
        storyboard = plan.get("storyboard", [])
        if isinstance(storyboard, list):
            _refresh_voiceover_clips(
                plan["timeline"],
                storyboard,
                render_root=render_root,
                tts_mode=tts_mode,
            )

    return plan
