from __future__ import annotations

import logging
import re
import wave
from pathlib import Path
from typing import Any

from app.pipelines.tts_mode import MASTER_TTS_SLOT_ID, VO_MASTER_CLIP_ID, is_global_tts_mode

logger = logging.getLogger(__name__)

_SUBTITLE_SENTENCE_SPLIT = re.compile(r"(?<=[。！？!?；\n])")
_MAX_SUBTITLE_CHARS = 28
_SUBTITLE_ID_PREFIXES = ("subtitle-",)


def wav_duration_sec(path: Path) -> float | None:
    """Read WAV duration; fall back to file-size estimate when headers are corrupt."""
    try:
        file_bytes = path.stat().st_size
    except OSError:
        file_bytes = 0
    try:
        with wave.open(str(path), "rb") as handle:
            rate = handle.getframerate()
            channels = handle.getnchannels()
            sample_width = handle.getsampwidth()
            if rate <= 0 or channels <= 0 or sample_width <= 0:
                return None
            header_duration = handle.getnframes() / float(rate)
            payload_bytes = max(0, file_bytes - 44)
            bytes_per_sec = rate * channels * sample_width
            size_duration = payload_bytes / bytes_per_sec if bytes_per_sec > 0 else None
            if size_duration is not None and size_duration > 0:
                if header_duration > size_duration * 1.25:
                    logger.warning(
                        "WAV header duration %.1fs exceeds payload estimate %.1fs for %s; using size estimate",
                        header_duration,
                        size_duration,
                        path.name,
                    )
                    return size_duration
            return header_duration
    except (OSError, wave.Error):
        return None


def chunk_subtitle_text(text: str, *, max_chars: int = _MAX_SUBTITLE_CHARS) -> list[str]:
    cleaned = text.strip()
    if not cleaned:
        return []
    parts = [
        part.strip()
        for part in _SUBTITLE_SENTENCE_SPLIT.split(cleaned)
        if part.strip()
    ]
    if not parts:
        parts = [cleaned]
    chunks: list[str] = []
    for part in parts:
        if len(part) <= max_chars:
            chunks.append(part)
            continue
        clause_parts = [
            segment.strip()
            for segment in re.split(r"(?<=[，,])", part)
            if segment.strip()
        ]
        buffer = ""
        for clause in clause_parts or [part]:
            candidate = f"{buffer}{clause}" if buffer else clause
            if len(candidate) <= max_chars:
                buffer = candidate
                continue
            if buffer:
                chunks.append(buffer)
            if len(clause) <= max_chars:
                buffer = clause
            else:
                for index in range(0, len(clause), max_chars):
                    chunks.append(clause[index : index + max_chars])
                buffer = ""
        if buffer:
            chunks.append(buffer)
    return chunks


def subtitle_time_windows(
    start_sec: float,
    end_sec: float,
    chunks: list[str],
) -> list[tuple[float, float, str]]:
    if not chunks:
        return []
    duration = max(0.1, float(end_sec) - float(start_sec))
    weights = [max(1, len(chunk)) for chunk in chunks]
    total_weight = sum(weights)
    windows: list[tuple[float, float, str]] = []
    cursor = float(start_sec)
    for index, chunk in enumerate(chunks):
        if index == len(chunks) - 1:
            windows.append((cursor, float(end_sec), chunk))
            break
        segment_duration = duration * (weights[index] / total_weight)
        windows.append((cursor, cursor + segment_duration, chunk))
        cursor += segment_duration
    return windows


def _subtitle_style_ref(packaging_plan: dict[str, Any]) -> str:
    preset = "clean"
    subtitle = packaging_plan.get("subtitle")
    if isinstance(subtitle, dict) and subtitle.get("preset"):
        preset = str(subtitle["preset"])
    return f"style://subtitle/{preset}"


def _is_subtitle_clip(clip: dict[str, Any]) -> bool:
    clip_id = str(clip.get("id", ""))
    return any(clip_id.startswith(prefix) for prefix in _SUBTITLE_ID_PREFIXES)


def strip_placeholder_subtitles(timeline: dict[str, Any]) -> dict[str, Any]:
    tracks = timeline.get("tracks", [])
    if not isinstance(tracks, list):
        return timeline
    for track in tracks:
        if not isinstance(track, dict) or track.get("type") != "text":
            continue
        clips = track.get("clips")
        if not isinstance(clips, list):
            continue
        track["clips"] = [
            clip for clip in clips if not (isinstance(clip, dict) and _is_subtitle_clip(clip))
        ]
    return timeline


def _text_track(tracks: list[Any]) -> dict[str, Any] | None:
    for track in tracks:
        if isinstance(track, dict) and track.get("type") == "text":
            return track
    return None


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


def _audible_window_for_vo_clip(
    vo_clip: dict[str, Any],
    *,
    render_root: Path | None,
) -> tuple[float, float] | None:
    start_sec = float(vo_clip.get("startSec", 0.0))
    end_sec = float(vo_clip.get("endSec", start_sec))
    source_ref = str(vo_clip.get("sourceRef", "")).strip()
    wav_path = _resolve_wav_path(source_ref, render_root)
    if wav_path is not None:
        duration = wav_duration_sec(wav_path)
        if duration is not None and duration > 0:
            end_sec = min(end_sec, start_sec + duration)
    if end_sec <= start_sec:
        return None
    return start_sec, end_sec


def _append_subtitle_clips(
    clips: list[dict[str, Any]],
    *,
    id_prefix: str,
    windows: list[tuple[float, float, str]],
    style_ref: str,
) -> None:
    for index, (start_sec, end_sec, content) in enumerate(windows):
        subtitle_id = (
            id_prefix
            if len(windows) == 1
            else f"{id_prefix}-{index + 1}"
        )
        clips.append(
            {
                "id": subtitle_id,
                "startSec": round(start_sec, 3),
                "endSec": round(end_sec, 3),
                "content": content,
                "styleRef": style_ref,
            }
        )


def align_subtitles_to_voiceover(
    timeline: dict[str, Any],
    storyboard: list[dict[str, Any]],
    packaging_plan: dict[str, Any],
    render_root: Path | None = None,
    *,
    master_narration: str = "",
    tts_mode: str | None = None,
) -> dict[str, Any]:
    """Rebuild subtitle clips using voiceover audible windows (post-TTS alignment)."""
    tracks = timeline.get("tracks", [])
    if not isinstance(tracks, list):
        return timeline

    style_ref = _subtitle_style_ref(packaging_plan)
    timeline = strip_placeholder_subtitles(timeline)

    text_track = _text_track(tracks)
    if text_track is None:
        text_track = {"id": "track-text", "type": "text", "clips": []}
        tracks.append(text_track)
    clips = text_track.setdefault("clips", [])

    voiceover_track = _voiceover_track(tracks)
    vo_by_id: dict[str, dict[str, Any]] = {}
    if voiceover_track is not None:
        for clip in voiceover_track.get("clips", []):
            if isinstance(clip, dict):
                vo_by_id[str(clip.get("id", ""))] = clip

    mode = tts_mode or "global"
    if is_global_tts_mode(mode) and str(master_narration).strip():
        vo_clip = vo_by_id.get(VO_MASTER_CLIP_ID)
        if vo_clip is None:
            wav_path = None
            if render_root is not None:
                candidate = render_root / "materials" / "master.wav"
                if candidate.is_file():
                    wav_path = candidate
            if wav_path is not None:
                duration = wav_duration_sec(wav_path)
                if duration and duration > 0:
                    window = (0.0, duration)
                else:
                    window = None
            else:
                window = None
                logger.warning("global TTS subtitles skipped: no vo-master clip or master.wav")
        else:
            window = _audible_window_for_vo_clip(vo_clip, render_root=render_root)

        if window is not None:
            chunks = chunk_subtitle_text(str(master_narration))
            windows = subtitle_time_windows(window[0], window[1], chunks)
            _append_subtitle_clips(
                clips,
                id_prefix="subtitle-master",
                windows=windows,
                style_ref=style_ref,
            )
        return timeline

    for scene in storyboard:
        if not isinstance(scene, dict):
            continue
        slot_id = str(scene.get("slotId", ""))
        script = str(scene.get("script", "")).strip()
        if not slot_id or not script:
            continue

        vo_clip = vo_by_id.get(f"vo-{slot_id}")
        window: tuple[float, float] | None = None
        if vo_clip is not None:
            window = _audible_window_for_vo_clip(vo_clip, render_root=render_root)
        elif render_root is not None:
            wav_path = render_root / "materials" / f"{slot_id}.wav"
            if wav_path.is_file():
                duration = wav_duration_sec(wav_path)
                if duration and duration > 0:
                    start_sec = float(scene.get("startSec", 0.0))
                    window = (start_sec, start_sec + duration)

        if window is None:
            logger.warning("subtitle alignment skipped for slot %s: no voiceover window", slot_id)
            continue

        chunks = chunk_subtitle_text(script)
        windows = subtitle_time_windows(window[0], window[1], chunks)
        _append_subtitle_clips(
            clips,
            id_prefix=f"subtitle-{slot_id}",
            windows=windows,
            style_ref=style_ref,
        )

    return timeline
