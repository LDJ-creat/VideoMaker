from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.render.aspect_ratio import render_dimensions
from app.render.timeline_compiler.audio_mixer import resolve_render_fps
from app.render.timeline_compiler.scene_segments import SceneSegment, resolve_segment_media_path
from app.render.timeline_compiler.transition_map import (
    resolve_transition_mode,
    transition_content_at_boundary,
    transition_duration_sec,
    xfade_transition_name,
)
from app.tools.ffmpeg_tool import FFmpegTool

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class VideoPiece:
    path: Path
    duration_sec: float
    is_scene: bool
    boundary_sec: float


def _tool_error(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "code": result.get("code", "ffmpeg_segment_failed"),
        "message": result.get("message", "ffmpeg segment build failed"),
        "retryable": bool(result.get("retryable", True)),
        "details": result.get("details", {}),
    }


def build_segment_clip(
    ffmpeg: FFmpegTool,
    segment: SceneSegment,
    *,
    render_root: Path,
    staging_dir: Path,
    width: int,
    height: int,
    fps: int,
) -> dict[str, Any]:
    staging_dir.mkdir(parents=True, exist_ok=True)
    raw_path = staging_dir / f"{segment.clip_id}-raw.mp4"
    scaled_path = staging_dir / f"{segment.clip_id}.mp4"
    duration = segment.duration_sec
    source_path = resolve_segment_media_path(render_root, segment)

    if source_path is None or segment.media_kind == "placeholder":
        result = ffmpeg.color_video(
            raw_path,
            duration_sec=duration,
            width=width,
            height=height,
            fps=fps,
        )
    elif segment.media_kind == "image":
        result = ffmpeg.still_image_to_video(
            source_path,
            raw_path,
            duration_sec=duration,
            fps=fps,
        )
    else:
        probe = ffmpeg.probe(source_path)
        source_duration = float(probe.get("durationSec") or duration) if not probe.get("code") else duration
        if source_duration >= duration - 0.05:
            result = ffmpeg.trim_clip(
                source_path,
                raw_path,
                start_sec=0.0,
                duration_sec=duration,
            )
        else:
            trimmed = staging_dir / f"{segment.clip_id}-trim.mp4"
            trim_result = ffmpeg.trim_clip(
                source_path,
                trimmed,
                start_sec=0.0,
                duration_sec=source_duration,
            )
            if trim_result.get("code"):
                return _tool_error(trim_result)
            result = ffmpeg.pad_video_duration(trimmed, raw_path, target_sec=duration)

    if result.get("code"):
        return _tool_error(result)

    scale_result = ffmpeg.scale_pad_video(
        raw_path,
        scaled_path,
        width=width,
        height=height,
        fps=fps,
    )
    if scale_result.get("code"):
        return _tool_error(scale_result)
    return {"path": str(scaled_path)}


def _build_gap_clip(
    ffmpeg: FFmpegTool,
    *,
    staging_dir: Path,
    gap_index: int,
    duration_sec: float,
    width: int,
    height: int,
    fps: int,
) -> dict[str, Any]:
    gap_path = staging_dir / f"gap-{gap_index}.mp4"
    return ffmpeg.color_video(
        gap_path,
        duration_sec=duration_sec,
        width=width,
        height=height,
        fps=fps,
    )


def _build_timeline_pieces(
    ffmpeg: FFmpegTool,
    segments: list[SceneSegment],
    *,
    render_root: Path,
    staging_dir: Path,
    width: int,
    height: int,
    fps: int,
) -> dict[str, Any]:
    ordered = sorted(segments, key=lambda item: (item.start_sec, item.clip_id))
    pieces: list[VideoPiece] = []
    cursor = 0.0
    gap_index = 0

    for segment in ordered:
        if segment.start_sec > cursor + 0.01:
            gap_duration = segment.start_sec - cursor
            gap_result = _build_gap_clip(
                ffmpeg,
                staging_dir=staging_dir,
                gap_index=gap_index,
                duration_sec=gap_duration,
                width=width,
                height=height,
                fps=fps,
            )
            gap_index += 1
            if gap_result.get("code"):
                return _tool_error(gap_result)
            cursor += gap_duration
            pieces.append(
                VideoPiece(
                    path=Path(gap_result["path"]),
                    duration_sec=gap_duration,
                    is_scene=False,
                    boundary_sec=cursor,
                )
            )

        built = build_segment_clip(
            ffmpeg,
            segment,
            render_root=render_root,
            staging_dir=staging_dir,
            width=width,
            height=height,
            fps=fps,
        )
        if built.get("code"):
            return built
        cursor = segment.end_sec
        pieces.append(
            VideoPiece(
                path=Path(built["path"]),
                duration_sec=segment.duration_sec,
                is_scene=True,
                boundary_sec=cursor,
            )
        )

    return {"pieces": pieces}


def _concat_hard(
    ffmpeg: FFmpegTool,
    clip_paths: list[Path],
    output_path: Path,
) -> dict[str, Any]:
    result = ffmpeg.concat_clips(clip_paths, output_path)
    if result.get("code"):
        return _tool_error(result)
    return {"path": str(output_path)}


def _xfade_two(
    ffmpeg: FFmpegTool,
    left: Path,
    right: Path,
    output_path: Path,
    *,
    left_duration: float,
    right_duration: float,
    fade_sec: float,
    transition_name: str,
) -> dict[str, Any]:
    offset = max(0.0, left_duration - fade_sec)
    filter_graph = (
        f"[0:v][1:v]xfade=transition={transition_name}:duration={fade_sec}:offset={offset}[outv]"
    )
    result = ffmpeg.run_filter_complex(
        inputs=[left, right],
        filter_graph=filter_graph,
        output_path=output_path,
        maps=["[outv]"],
        extra_args=["-c:v", "libx264", "-pix_fmt", "yuv420p", "-an"],
    )
    if result.get("code"):
        return _tool_error(result)
    merged_duration = left_duration + right_duration - fade_sec
    probe = ffmpeg.probe(output_path)
    if not probe.get("code"):
        merged_duration = float(probe.get("durationSec") or merged_duration)
    return {"path": str(output_path), "durationSec": merged_duration}


def _merge_two_pieces(
    ffmpeg: FFmpegTool,
    left: VideoPiece,
    right: VideoPiece,
    output_path: Path,
    *,
    transition_clips: list[dict[str, Any]],
    mode: str,
) -> dict[str, Any]:
    use_xfade = (
        mode in {"xfade", "overlay_fade"}
        and left.is_scene
        and right.is_scene
    )
    if use_xfade:
        content = transition_content_at_boundary(transition_clips, left.boundary_sec)
        fade_sec = transition_duration_sec(content, mode=mode)  # type: ignore[arg-type]
        if fade_sec > 0:
            transition_name = xfade_transition_name(content)
            merged = _xfade_two(
                ffmpeg,
                left.path,
                right.path,
                output_path,
                left_duration=left.duration_sec,
                right_duration=right.duration_sec,
                fade_sec=fade_sec,
                transition_name=transition_name,
            )
            if not merged.get("code"):
                merged_duration = float(
                    merged.get("durationSec") or (left.duration_sec + right.duration_sec - fade_sec)
                )
                return {
                    "path": merged["path"],
                    "piece": VideoPiece(
                        path=Path(merged["path"]),
                        duration_sec=merged_duration,
                        is_scene=True,
                        boundary_sec=right.boundary_sec,
                    ),
                }
            logger.warning(
                "xfade merge failed at %.2fs, falling back to hard cut: %s",
                left.boundary_sec,
                merged.get("message"),
            )

    concat_result = _concat_hard(ffmpeg, [left.path, right.path], output_path)
    if concat_result.get("code"):
        return concat_result
    return {
        "path": concat_result["path"],
        "piece": VideoPiece(
            path=Path(concat_result["path"]),
            duration_sec=left.duration_sec + right.duration_sec,
            is_scene=left.is_scene and right.is_scene,
            boundary_sec=right.boundary_sec,
        ),
    }


def _concat_pieces(
    ffmpeg: FFmpegTool,
    pieces: list[VideoPiece],
    output_path: Path,
    *,
    transition_clips: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    if not pieces:
        return {"code": "ffmpeg_concat_empty", "message": "No video pieces", "retryable": False}
    if len(pieces) == 1:
        if pieces[0].path.resolve() != output_path.resolve():
            output_path.write_bytes(pieces[0].path.read_bytes())
        return {"path": str(output_path)}

    mode = resolve_transition_mode()
    if mode == "cut":
        return _concat_hard(ffmpeg, [piece.path for piece in pieces], output_path)

    staging_dir = output_path.parent
    current = pieces[0]
    merge_index = 0
    for nxt in pieces[1:]:
        merged_path = staging_dir / f"merged-{merge_index}.mp4"
        merge_index += 1
        merged = _merge_two_pieces(
            ffmpeg,
            current,
            nxt,
            merged_path,
            transition_clips=transition_clips or [],
            mode=mode,
        )
        if merged.get("code"):
            return merged
        current = merged["piece"]

    if Path(current.path).resolve() != output_path.resolve():
        output_path.write_bytes(Path(current.path).read_bytes())
    return {"path": str(output_path)}


def build_video_track(
    ffmpeg: FFmpegTool,
    segments: list[SceneSegment],
    *,
    render_root: Path,
    staging_dir: Path,
    output_path: Path,
    aspect_ratio: str,
    transition_clips: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    width, height = render_dimensions(aspect_ratio)
    fps = resolve_render_fps()

    if not segments:
        return ffmpeg.color_video(
            output_path,
            duration_sec=1.0,
            width=width,
            height=height,
            fps=fps,
        )

    built = _build_timeline_pieces(
        ffmpeg,
        segments,
        render_root=render_root,
        staging_dir=staging_dir,
        width=width,
        height=height,
        fps=fps,
    )
    if built.get("code"):
        return built

    return _concat_pieces(
        ffmpeg,
        built["pieces"],
        output_path,
        transition_clips=transition_clips,
    )


def pad_video_to_duration(
    ffmpeg: FFmpegTool,
    video_path: Path,
    output_path: Path,
    target_sec: float,
) -> dict[str, Any]:
    result = ffmpeg.pad_video_duration(video_path, output_path, target_sec=target_sec)
    if result.get("code"):
        return _tool_error(result)
    return {"path": str(output_path)}
