from __future__ import annotations

from pathlib import Path
from typing import Any

from app.render.aspect_ratio import subtitle_layout
from app.render.render_timeline_to_hyperframes import KNOWN_SUBTITLE_PRESETS, _subtitle_class

_SUBTITLE_PREFIX = "subtitle-"


def _format_ass_time(seconds: float) -> str:
    total_cs = max(0, int(round(float(seconds) * 100)))
    cs = total_cs % 100
    total_s = total_cs // 100
    s = total_s % 60
    total_m = total_s // 60
    m = total_m % 60
    h = total_m // 60
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _escape_ass_text(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace("{", "\\{")
        .replace("}", "\\}")
        .replace("\n", "\\N")
    )


def _style_name_from_ref(style_ref: str) -> str:
    preset = "clean"
    marker = "style://subtitle/"
    if style_ref.startswith(marker):
        preset = style_ref[len(marker) :] or "clean"
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in preset)
    if safe not in KNOWN_SUBTITLE_PRESETS:
        safe = "clean"
    return f"Subtitle_{safe}"


def _style_block(name: str, aspect_ratio: str) -> str:
    layout = subtitle_layout(aspect_ratio)
    font_size = layout["fontSizePx"]
    margin_v = layout["bottomPaddingPx"]
    margin_l = layout["sidePaddingPx"]
    margin_r = layout["sidePaddingPx"]
    if name.endswith("_bold"):
        return (
            f"Style: {name},Arial,{font_size + 4},&H00FFFFFF,&H000000FF,&H00000000,"
            f"&H96000000,-1,0,0,0,100,100,0,0,1,3,2,2,{margin_l},{margin_r},{margin_v},1"
        )
    if name.endswith("_minimal"):
        return (
            f"Style: {name},Arial,{font_size - 2},&H00FFFFFF,&H000000FF,&H00000000,"
            f"&H00000000,0,0,0,0,100,100,0,0,1,1,1,2,{margin_l},{margin_r},{margin_v},1"
        )
    return (
        f"Style: {name},Arial,{font_size},&H00FFFFFF,&H000000FF,&H00000000,"
        f"&H80000000,-1,0,0,0,100,100,0,0,1,2,2,2,{margin_l},{margin_r},{margin_v},1"
    )


def collect_subtitle_clips(timeline: dict[str, Any]) -> list[dict[str, Any]]:
    tracks = timeline.get("tracks", [])
    if not isinstance(tracks, list):
        return []
    subtitles: list[dict[str, Any]] = []
    for track in tracks:
        if not isinstance(track, dict) or track.get("type") != "text":
            continue
        for clip in track.get("clips", []):
            if not isinstance(clip, dict):
                continue
            clip_id = str(clip.get("id", ""))
            if not clip_id.startswith(_SUBTITLE_PREFIX):
                continue
            content = str(clip.get("content", "")).strip()
            if not content:
                continue
            subtitles.append(clip)
    return sorted(subtitles, key=lambda item: (float(item.get("startSec", 0)), str(item.get("id", ""))))


def write_ass_subtitles(
    timeline: dict[str, Any],
    output_path: Path,
    *,
    aspect_ratio: str = "9:16",
    play_res: tuple[int, int] = (1080, 1920),
) -> bool:
    clips = collect_subtitle_clips(timeline)
    if not clips:
        return False

    width, height = play_res
    style_names: dict[str, str] = {}
    style_lines: list[str] = []
    for clip in clips:
        style_ref = str(clip.get("styleRef", ""))
        css_class = _subtitle_class(style_ref) if style_ref else "subtitle-clean"
        preset = css_class.removeprefix("subtitle-") or "clean"
        style_name = f"Subtitle_{preset}"
        if style_name not in style_names:
            style_names[style_name] = style_name
            style_lines.append(_style_block(style_name, aspect_ratio))

    events: list[str] = []
    for clip in clips:
        style_ref = str(clip.get("styleRef", ""))
        css_class = _subtitle_class(style_ref) if style_ref else "subtitle-clean"
        preset = css_class.removeprefix("subtitle-") or "clean"
        style_name = f"Subtitle_{preset}"
        start = _format_ass_time(float(clip.get("startSec", 0.0)))
        end = _format_ass_time(float(clip.get("endSec", 0.0)))
        text = _escape_ass_text(str(clip.get("content", "")))
        events.append(f"Dialogue: 0,{start},{end},{style_name},,0,0,0,,{text}")

    header = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {width}",
        f"PlayResY: {height}",
        "WrapStyle: 0",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        *style_lines,
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        *events,
        "",
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(header), encoding="utf-8-sig")
    return True
