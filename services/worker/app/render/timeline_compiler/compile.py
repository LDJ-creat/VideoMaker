from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.render.aspect_ratio import render_dimensions
from app.render.timeline_compiler.audio_mixer import (
    collect_bgm_specs,
    collect_voiceover_specs,
    resolve_bgm_volume,
)
from app.render.timeline_compiler.hold_tail import apply_hold_tail_to_segments, timeline_target_duration
from app.render.timeline_compiler.normalize import normalize_timeline
from app.render.timeline_compiler.scene_segments import extract_scene_segments
from app.render.timeline_compiler.subtitle_ass import write_ass_subtitles
from app.render.timeline_compiler.video_builder import build_video_track, pad_video_to_duration
from app.tools.ffmpeg_tool import FFmpegTool

logger = logging.getLogger(__name__)

ProgressEmitter = Callable[[str], None]


@dataclass(slots=True)
class CompileResult:
    ok: bool
    output_path: Path | None = None
    log: dict[str, Any] = field(default_factory=dict)
    error: dict[str, Any] | None = None


def _collect_transition_clips(timeline: dict[str, Any]) -> list[dict[str, Any]]:
    tracks = timeline.get("tracks", [])
    if not isinstance(tracks, list):
        return []
    clips: list[dict[str, Any]] = []
    for track in tracks:
        if isinstance(track, dict) and track.get("type") == "transition":
            for clip in track.get("clips", []):
                if isinstance(clip, dict):
                    clips.append(clip)
    return sorted(clips, key=lambda item: float(item.get("startSec", 0)))


def _compile_fail(log: dict[str, Any], error: dict[str, Any]) -> CompileResult:
    log["status"] = "failed"
    return CompileResult(ok=False, log=log, error=error)


def compile_timeline_to_mp4(
    timeline: dict[str, Any],
    *,
    render_root: Path,
    output_path: Path,
    aspect_ratio: str = "9:16",
    ffmpeg: FFmpegTool | None = None,
    tts_mode: str | None = None,
    emit_progress: ProgressEmitter | None = None,
) -> CompileResult:
    started = time.perf_counter()
    tool = ffmpeg or FFmpegTool()
    staging_dir = render_root / "ffmpeg-staging"
    staging_dir.mkdir(parents=True, exist_ok=True)

    normalized = normalize_timeline(timeline)
    segments = extract_scene_segments(normalized, render_root=render_root)
    target_duration = timeline_target_duration(normalized, segments)
    segments = apply_hold_tail_to_segments(segments, target_duration)

    stage_timings: dict[str, int] = {}
    log: dict[str, Any] = {
        "backend": "ffmpeg",
        "segmentCount": len(segments),
        "targetDurationSec": round(target_duration, 3),
        "warnings": [],
    }

    if emit_progress is not None:
        emit_progress("video_build")

    stage_start = time.perf_counter()
    video_staged = staging_dir / "video-base.mp4"
    video_result = build_video_track(
        tool,
        segments,
        render_root=render_root,
        staging_dir=staging_dir,
        output_path=video_staged,
        aspect_ratio=aspect_ratio,
        transition_clips=_collect_transition_clips(normalized),
    )
    if video_result.get("code"):
        return _compile_fail(log, video_result)
    stage_timings["videoBuildMs"] = round((time.perf_counter() - stage_start) * 1000)

    if emit_progress is not None:
        emit_progress("hold_tail")

    stage_start = time.perf_counter()
    video_padded = staging_dir / "video-padded.mp4"
    pad_result = pad_video_to_duration(
        tool,
        Path(video_result["path"]),
        video_padded,
        target_duration,
    )
    if pad_result.get("code"):
        return _compile_fail(log, pad_result)
    stage_timings["holdTailMs"] = round((time.perf_counter() - stage_start) * 1000)

    if emit_progress is not None:
        emit_progress("audio_mix")

    stage_start = time.perf_counter()
    vo_specs = collect_voiceover_specs(
        normalized,
        render_root=render_root,
        target_duration_sec=target_duration,
        tts_mode=tts_mode,
    )
    bgm_specs = collect_bgm_specs(
        normalized,
        render_root=render_root,
        volume=resolve_bgm_volume(),
    )
    audio_path = staging_dir / "mixed-audio.m4a"
    has_audio = bool(vo_specs or bgm_specs)
    if has_audio:
        mix_result = tool.mix_audio_tracks(
            output_path=audio_path,
            voiceover_specs=vo_specs,
            bgm_specs=bgm_specs,
            duration_sec=target_duration,
        )
        if mix_result.get("code"):
            return _compile_fail(log, mix_result)
    stage_timings["audioMixMs"] = round((time.perf_counter() - stage_start) * 1000)

    if emit_progress is not None:
        emit_progress("subtitles")

    stage_start = time.perf_counter()
    width, height = render_dimensions(aspect_ratio)
    ass_path = staging_dir / "subtitles.ass"
    has_subtitles = write_ass_subtitles(
        normalized,
        ass_path,
        aspect_ratio=aspect_ratio,
        play_res=(width, height),
    )

    current_video = Path(pad_result["path"])
    if has_subtitles:
        subtitled = staging_dir / "video-subtitled.mp4"
        sub_result = tool.burn_subtitles(current_video, ass_path, subtitled, copy_audio=False)
        if sub_result.get("code"):
            return _compile_fail(log, sub_result)
        current_video = Path(sub_result["path"])
    stage_timings["subtitlesMs"] = round((time.perf_counter() - stage_start) * 1000)

    if emit_progress is not None:
        emit_progress("mux")

    stage_start = time.perf_counter()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if has_audio:
        mux_result = tool.mux_video_audio(
            current_video,
            audio_path,
            output_path,
            duration_sec=target_duration,
        )
        if mux_result.get("code"):
            return _compile_fail(log, mux_result)
    else:
        output_path.write_bytes(current_video.read_bytes())

    stage_timings["muxMs"] = round((time.perf_counter() - stage_start) * 1000)
    log["stageTimingsMs"] = stage_timings
    log["voiceoverClipCount"] = len(vo_specs)
    log["bgmClipCount"] = len(bgm_specs)
    log["durationMs"] = round((time.perf_counter() - started) * 1000)
    log["status"] = "succeeded"

    if not output_path.is_file() or output_path.stat().st_size == 0:
        return _compile_fail(
            log,
            {
                "code": "ffmpeg_render_empty_output",
                "message": "FFmpeg render produced no output",
                "retryable": True,
            },
        )

    return CompileResult(ok=True, output_path=output_path, log=log)
