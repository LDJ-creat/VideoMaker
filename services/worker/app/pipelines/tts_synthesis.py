from __future__ import annotations

import io
import json
import wave
from pathlib import Path
from typing import Any

from knowledge.paths import validate_storage_segment

from app.pipelines.narration_alignment import wav_duration_sec
from app.pipelines.tts_voice_options import (
    build_tts_synthesis_options,
    canonical_tts_options_key,
)
from app.tools.tts_tool import TTSTool


def _safe_segment_filename(slot_id: str, *, index: int) -> str:
    try:
        return validate_storage_segment(str(slot_id), field="slotId")
    except ValueError:
        return f"scene-{index}"


def _scenes_with_script(storyboard: list[dict[str, Any]]) -> list[dict[str, Any]]:
    scenes: list[dict[str, Any]] = []
    for scene in storyboard:
        if not isinstance(scene, dict):
            continue
        script = str(scene.get("script") or "").strip()
        if script:
            scenes.append(scene)
    return scenes


def _segment_options_for_storyboard(
    *,
    storyboard: list[dict[str, Any]],
    structure: dict[str, Any],
    workbench_prefs: dict[str, Any],
    generation_id: str,
    narration_vo_profile: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    scenes = _scenes_with_script(storyboard)
    segment_options: list[dict[str, Any]] = []
    for scene in scenes:
        segment_options.append(
            build_tts_synthesis_options(
                structure=structure,
                workbench_prefs=workbench_prefs,
                generation_id=generation_id,
                narration_vo_profile=narration_vo_profile,
                scene_vo_directive=scene.get("voDirective")
                if isinstance(scene.get("voDirective"), dict)
                else None,
            )
        )
    return segment_options


def resolve_synthesis_mode(
    *,
    storyboard: list[dict[str, Any]],
    structure: dict[str, Any],
    workbench_prefs: dict[str, Any],
    generation_id: str,
    narration_vo_profile: dict[str, Any] | None,
) -> str:
    segment_options = _segment_options_for_storyboard(
        storyboard=storyboard,
        structure=structure,
        workbench_prefs=workbench_prefs,
        generation_id=generation_id,
        narration_vo_profile=narration_vo_profile,
    )
    if not segment_options:
        return "single_shot"
    unique_keys = {canonical_tts_options_key(item) for item in segment_options}
    return "single_shot" if len(unique_keys) == 1 else "segmented"


def _segment_slot_hash(scene: dict[str, Any], options: dict[str, Any]) -> str:
    payload = {
        "script": str(scene.get("script") or "").strip(),
        "voDirective": scene.get("voDirective") if isinstance(scene.get("voDirective"), dict) else None,
        "ttsOptionsKey": canonical_tts_options_key(options),
    }
    import hashlib

    digest = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return f"sha256:{digest}"


def _write_segment_meta(
    segment_cache_dir: Path,
    entries: list[dict[str, Any]],
) -> None:
    segment_cache_dir.parent.mkdir(parents=True, exist_ok=True)
    meta_path = segment_cache_dir.parent / "segment-meta.json"
    meta_path.write_text(json.dumps({"segments": entries}, ensure_ascii=False, indent=2), encoding="utf-8")


def _concat_wav_bytes(parts: list[bytes]) -> bytes:
    if not parts:
        return b""
    if len(parts) == 1:
        return parts[0]

    params_set: tuple[int, int, int] | None = None
    frames: list[bytes] = []
    for blob in parts:
        with wave.open(io.BytesIO(blob), "rb") as handle:
            current = (handle.getnchannels(), handle.getsampwidth(), handle.getframerate())
            if params_set is None:
                params_set = current
            elif current != params_set:
                raise ValueError("incompatible_wav_segments_for_concat")
            frames.append(handle.readframes(handle.getnframes()))

    assert params_set is not None
    channels, sample_width, frame_rate = params_set
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as out:
        out.setnchannels(channels)
        out.setsampwidth(sample_width)
        out.setframerate(frame_rate)
        for chunk in frames:
            out.writeframes(chunk)
    return buffer.getvalue()


def synthesize_master_wav(
    *,
    tool: TTSTool,
    master_narration: str,
    storyboard: list[dict[str, Any]],
    structure: dict[str, Any],
    workbench_prefs: dict[str, Any],
    generation_id: str,
    narration_vo_profile: dict[str, Any] | None,
    output_path: Path,
    segment_cache_dir: Path | None = None,
    changed_slot_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Synthesize global master.wav with optional per-scene voDirective segments."""
    text = str(master_narration or "").strip()
    if not text:
        raise ValueError("master_narration is required for global TTS")

    scenes = _scenes_with_script(storyboard)
    if not scenes:
        options = build_tts_synthesis_options(
            structure=structure,
            workbench_prefs=workbench_prefs,
            generation_id=generation_id,
            narration_vo_profile=narration_vo_profile,
        )
        return tool.synthesize(text=text, output_path=output_path, options=options)

    segment_options = _segment_options_for_storyboard(
        storyboard=storyboard,
        structure=structure,
        workbench_prefs=workbench_prefs,
        generation_id=generation_id,
        narration_vo_profile=narration_vo_profile,
    )

    unique_keys = {canonical_tts_options_key(item) for item in segment_options}
    if len(unique_keys) == 1:
        if changed_slot_ids:
            pass  # single_shot ignores incremental slot ids
        return tool.synthesize(
            text=text,
            output_path=output_path,
            options=segment_options[0],
        )

    import os

    incremental = (
        os.getenv("VIDEOMAKER_TTS_SEGMENT_INCREMENTAL", "false").strip().lower() == "true"
    )
    meta_by_slot: dict[str, dict[str, Any]] = {}
    if segment_cache_dir is not None:
        meta_path = segment_cache_dir.parent / "segment-meta.json"
        if meta_path.is_file():
            try:
                meta_payload = json.loads(meta_path.read_text(encoding="utf-8"))
                if isinstance(meta_payload, dict):
                    for entry in meta_payload.get("segments") or []:
                        if isinstance(entry, dict) and entry.get("slotId"):
                            meta_by_slot[str(entry["slotId"])] = entry
            except json.JSONDecodeError:
                meta_by_slot = {}

    wav_parts: list[bytes] = []
    segment_durations: list[tuple[str, float]] = []
    meta_entries: list[dict[str, Any]] = []
    for index, (scene, options) in enumerate(zip(scenes, segment_options, strict=True)):
        segment_text = str(scene.get("script") or "").strip()
        slot_id = str(scene.get("slotId") or "slot")
        safe_slot = _safe_segment_filename(slot_id, index=index)
        segment_hash = _segment_slot_hash(scene, options)
        cached_path = (
            (segment_cache_dir / f"{safe_slot}.wav") if segment_cache_dir is not None else None
        )
        should_resynth = not incremental
        if incremental:
            if changed_slot_ids is not None and slot_id in changed_slot_ids:
                should_resynth = True
            elif cached_path is None or not cached_path.is_file():
                should_resynth = True
            else:
                cached_meta = meta_by_slot.get(slot_id)
                should_resynth = not (
                    isinstance(cached_meta, dict) and cached_meta.get("contentHash") == segment_hash
                )
        if (
            not should_resynth
            and cached_path is not None
            and cached_path.is_file()
            and cached_path.stat().st_size > 0
        ):
            wav_parts.append(cached_path.read_bytes())
            segment_durations.append((slot_id, wav_duration_sec(cached_path)))
            meta_entries.append(
                {"slotId": slot_id, "contentHash": segment_hash, "durationSec": segment_durations[-1][1]}
            )
            continue

        temp_path = (
            cached_path
            if cached_path is not None
            else output_path.parent / f".segment-{safe_slot}.wav"
        )
        try:
            tool.synthesize(text=segment_text, output_path=temp_path, options=options)
            wav_parts.append(temp_path.read_bytes())
            duration = wav_duration_sec(temp_path)
            segment_durations.append((slot_id, duration))
            meta_entries.append(
                {"slotId": slot_id, "contentHash": segment_hash, "durationSec": duration}
            )
        finally:
            if cached_path is None and temp_path.is_file():
                temp_path.unlink()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(_concat_wav_bytes(wav_parts))
    if segment_cache_dir is not None:
        _write_segment_meta(segment_cache_dir, meta_entries)
    from app.tools.image_gen_tool import _artifact_ref

    artifact = _artifact_ref("audio", output_path)
    artifact["segmentDurations"] = segment_durations
    artifact["synthesisMode"] = "segmented"
    return artifact
