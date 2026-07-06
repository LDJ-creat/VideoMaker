from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any

from app.gateway.model_gateway import ModelGateway
from app.pipelines.narration_alignment import wav_duration_sec
from app.pipelines.narration_scene_timing import (
    allocate_scene_windows_from_whisper,
    apply_narration_timing_to_storyboard,
    canonical_content_hash,
    load_narration_timing,
    narration_timing_is_current,
    narration_timing_path,
    reconcile_storyboard_to_segment_durations,
    save_narration_timing,
    transcribe_preview_wav,
)
from app.agents.runner import AgentRunner
from app.pipelines.narration_drift import run_narration_drift_resolution, save_estimated_snapshot
from app.pipelines.script_draft import load_script_draft, save_script_draft
from app.pipelines.tts_synthesis import resolve_synthesis_mode, synthesize_master_wav
from app.runtime.task_context import TaskContext
from app.tools.tts_tool import TTSTool

CANONICAL_WAV_REL = "narration/canonical.wav"
SEGMENT_META_FILENAME = "segment-meta.json"


def canonical_wav_path(generation_root: Path) -> Path:
    return generation_root / CANONICAL_WAV_REL


def segment_cache_dir(generation_root: Path) -> Path:
    return generation_root / "narration" / "segments"


def invalidate_narration_timing(generation_root: Path) -> None:
    from app.pipelines.narration_scene_timing import (
        clear_narration_preview,
        unmark_checkpoint_stage,
    )

    timing_path = narration_timing_path(generation_root)
    if timing_path.is_file():
        timing_path.unlink()
    canonical = canonical_wav_path(generation_root)
    if canonical.is_file():
        canonical.unlink()
    segments_dir = segment_cache_dir(generation_root)
    if segments_dir.is_dir():
        shutil.rmtree(segments_dir, ignore_errors=True)
    meta_path = generation_root / "narration" / SEGMENT_META_FILENAME
    if meta_path.is_file():
        meta_path.unlink()
    drift_path = generation_root / "narration" / "drift-report.json"
    if drift_path.is_file():
        drift_path.unlink()
    clear_narration_preview(generation_root)
    unmark_checkpoint_stage(generation_root, "narration_preview")
    unmark_checkpoint_stage(generation_root, "synthesizing_canonical_narration")
    unmark_checkpoint_stage(generation_root, "adapting_narration_density")
    unmark_checkpoint_stage(generation_root, "planning_completion")
    draft = load_script_draft(generation_root)
    if isinstance(draft, dict):
        updated = dict(draft)
        updated["narrationTimingStatus"] = "stale"
        updated.pop("narrationDurationSec", None)
        save_script_draft(generation_root, updated)


def _alignment_from_artifact(
    artifact: dict[str, Any],
    *,
    draft: dict[str, Any],
    structure: dict[str, Any],
    whisper_segments: list[dict[str, Any]],
    duration_sec: float,
) -> tuple[list[dict[str, Any]], str, list[str]]:
    segment_durations = artifact.get("segmentDurations")
    if isinstance(segment_durations, list) and segment_durations:
        storyboard = [
            dict(scene) for scene in draft.get("storyboard") or [] if isinstance(scene, dict)
        ]
        aligned = reconcile_storyboard_to_segment_durations(
            storyboard,
            segment_durations=[
                (str(slot_id), float(duration))
                for slot_id, duration in segment_durations
                if slot_id and float(duration) > 0
            ],
        )
        scene_timing = [
            {
                "slotId": str(scene.get("slotId", "")),
                "startSec": float(scene.get("startSec", 0.0)),
                "endSec": float(scene.get("endSec", 0.0)),
            }
            for scene in aligned
            if scene.get("slotId")
        ]
        return scene_timing, "segment_durations", []

    scene_timing, alignment_method, warnings = allocate_scene_windows_from_whisper(
        master_narration=str(draft.get("masterNarration") or ""),
        structure=structure,
        whisper_segments=whisper_segments,
        total_duration_sec=float(duration_sec),
    )
    return scene_timing, alignment_method, list(warnings)


def run_canonical_narration_synthesis(
    *,
    gateway: ModelGateway,
    structure: dict[str, Any],
    context: TaskContext,
    generation_id: str,
    generation_root: Path,
    draft: dict[str, Any] | None = None,
    changed_slot_ids: set[str] | None = None,
    force: bool = False,
    runner: AgentRunner | None = None,
) -> dict[str, Any]:
    """Synthesize authoritative narration/canonical.wav after storyboard approval."""
    loaded = draft or load_script_draft(generation_root)
    if loaded is None:
        raise ValueError("script-draft.json not found")
    draft_payload = dict(loaded)

    if not force and narration_timing_is_current(
        generation_root,
        draft_payload,
        structure=structure,
        workbench_prefs=gateway.config.tts_preferences,
        generation_id=generation_id,
    ):
        existing = load_narration_timing(generation_root)
        assert existing is not None
        return existing

    context.emit_event(
        stage="synthesizing_canonical_narration",
        progress=54,
        message="Synthesizing canonical narration audio",
    )

    output_path = canonical_wav_path(generation_root)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cache_dir = segment_cache_dir(generation_root)
    cache_dir.mkdir(parents=True, exist_ok=True)

    tool = TTSTool(gateway=gateway, emit_progress=context.emit_progress)
    storyboard = [
        dict(scene) for scene in draft_payload.get("storyboard") or [] if isinstance(scene, dict)
    ]
    artifact = synthesize_master_wav(
        tool=tool,
        master_narration=str(draft_payload.get("masterNarration") or ""),
        storyboard=storyboard,
        structure=structure,
        workbench_prefs=gateway.config.tts_preferences,
        generation_id=generation_id,
        narration_vo_profile=(
            draft_payload.get("narrationVoProfile")
            if isinstance(draft_payload.get("narrationVoProfile"), dict)
            else None
        ),
        output_path=output_path,
        segment_cache_dir=cache_dir,
        changed_slot_ids=changed_slot_ids,
    )

    duration_sec = wav_duration_sec(output_path)
    if duration_sec is None or duration_sec <= 0:
        raise ValueError("canonical_narration_duration_unavailable")

    context.emit_event(
        stage="aligning_narration_timing",
        progress=55,
        message="Aligning canonical narration timing",
    )
    whisper_segments, transcribe_warnings = transcribe_preview_wav(output_path)
    scene_timing, alignment_method, align_warnings = _alignment_from_artifact(
        artifact,
        draft=draft_payload,
        structure=structure,
        whisper_segments=whisper_segments,
        duration_sec=duration_sec,
    )

    synthesis_mode = resolve_synthesis_mode(
        storyboard=storyboard,
        structure=structure,
        workbench_prefs=gateway.config.tts_preferences,
        generation_id=generation_id,
        narration_vo_profile=(
            draft_payload.get("narrationVoProfile")
            if isinstance(draft_payload.get("narrationVoProfile"), dict)
            else None
        ),
    )

    segment_payload: list[dict[str, Any]] | None = None
    raw_segments = artifact.get("segmentDurations")
    if isinstance(raw_segments, list):
        segment_payload = [
            {"slotId": str(slot_id), "durationSec": round(float(duration), 3)}
            for slot_id, duration in raw_segments
            if slot_id and float(duration) > 0
        ]

    content_hash = canonical_content_hash(
        draft_payload,
        structure=structure,
        workbench_prefs=gateway.config.tts_preferences,
        generation_id=generation_id,
    )
    timing: dict[str, Any] = {
        "role": "canonical",
        "contentHash": content_hash,
        "durationSec": round(float(duration_sec), 3),
        "wavUri": CANONICAL_WAV_REL,
        "alignmentMethod": alignment_method,
        "synthesisMode": synthesis_mode,
        "sceneTiming": scene_timing,
        "warnings": list(dict.fromkeys([*align_warnings, *transcribe_warnings])),
    }
    if segment_payload:
        timing["segmentDurations"] = segment_payload

    save_narration_timing(generation_root, timing)

    save_estimated_snapshot(generation_root, storyboard)
    updated_storyboard = apply_narration_timing_to_storyboard(storyboard, scene_timing)
    draft_payload["storyboard"] = updated_storyboard
    draft_payload["narrationDurationSec"] = round(float(duration_sec), 3)
    draft_payload["narrationTimingStatus"] = "canonical"
    save_script_draft(generation_root, draft_payload)

    run_narration_drift_resolution(
        generation_root=generation_root,
        structure=structure,
        timing=timing,
        context=context,
        generation_id=generation_id,
        runner=runner,
    )

    if os.getenv("VIDEOMAKER_CANONICAL_WHISPER_AFTER_SCRIPT", "false").strip().lower() == "true":
        pass  # whisper already run above; flag reserved for incremental-only path

    return timing
