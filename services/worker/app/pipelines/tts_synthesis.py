from __future__ import annotations

import io
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

    unique_keys = {canonical_tts_options_key(item) for item in segment_options}
    if len(unique_keys) == 1:
        return tool.synthesize(
            text=text,
            output_path=output_path,
            options=segment_options[0],
        )

    wav_parts: list[bytes] = []
    segment_durations: list[tuple[str, float]] = []
    for index, (scene, options) in enumerate(zip(scenes, segment_options, strict=True)):
        segment_text = str(scene.get("script") or "").strip()
        slot_id = str(scene.get("slotId") or "slot")
        safe_slot = _safe_segment_filename(slot_id, index=index)
        temp_path = output_path.parent / f".segment-{safe_slot}.wav"
        try:
            tool.synthesize(text=segment_text, output_path=temp_path, options=options)
            wav_parts.append(temp_path.read_bytes())
            segment_durations.append((slot_id, wav_duration_sec(temp_path)))
        finally:
            if temp_path.is_file():
                temp_path.unlink()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(_concat_wav_bytes(wav_parts))
    from app.tools.image_gen_tool import _artifact_ref

    artifact = _artifact_ref("audio", output_path)
    artifact["segmentDurations"] = segment_durations
    return artifact
