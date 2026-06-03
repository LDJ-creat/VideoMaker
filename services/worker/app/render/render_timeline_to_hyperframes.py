from __future__ import annotations

import html
import json
import os
from pathlib import Path
from typing import Any

COMPOSITION_ID = "videomaker-main"
DEFAULT_WIDTH = 1080
DEFAULT_HEIGHT = 1920

TRACK_ORDER = {
    "video": 0,
    "image": 1,
    "text": 2,
    "effect": 3,
    "transition": 4,
    "voiceover": 5,
    "bgm": 6,
}


def _format_sec(seconds: float) -> str:
    value = float(seconds)
    if value == int(value):
        return str(int(value))
    return f"{value:g}"


def _clip_duration_sec(clip: dict[str, Any]) -> float:
    return max(0.0, float(clip["endSec"]) - float(clip["startSec"]))


def _is_image_source_ref(source_ref: str) -> bool:
    lowered = source_ref.lower()
    return lowered.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"))


def _is_video_source_ref(source_ref: str) -> bool:
    lowered = source_ref.lower()
    return lowered.endswith((".mp4", ".webm", ".mov", ".mkv"))


def _safe_asset_path(render_root: Path, composition_dir: Path, source_ref: str) -> str:
    candidate = (render_root / source_ref).resolve()
    root = render_root.resolve()
    if not candidate.is_relative_to(root):
        raise ValueError("sourceRef escapes render directory")
    return Path(
        os.path.relpath(candidate, composition_dir.resolve())
    ).as_posix()


def _embed_timeline_json(timeline: dict[str, Any]) -> str:
    """Serialize timeline for inline <script> without breaking out of the tag."""
    serialized = json.dumps(timeline, ensure_ascii=False)
    return serialized.replace("<", "\\u003c").replace(">", "\\u003e")


def _normalize_timeline(timeline: dict[str, Any]) -> dict[str, Any]:
    tracks = list(timeline.get("tracks", []))
    ordered_tracks = sorted(
        tracks,
        key=lambda t: (TRACK_ORDER.get(t.get("type", ""), 999), str(t.get("id", ""))),
    )

    normalized: list[dict[str, Any]] = []
    for track in ordered_tracks:
        clips = list(track.get("clips", []))
        ordered_clips = sorted(
            clips,
            key=lambda c: (float(c.get("startSec", 0)), str(c.get("id", ""))),
        )
        normalized.append(
            {
                "id": track.get("id"),
                "type": track.get("type"),
                "clips": ordered_clips,
            }
        )
    return {"durationSec": timeline.get("durationSec", 0), "tracks": normalized}


def _build_gsap_visibility_script(normalized: dict[str, Any]) -> str:
    """Drive clip visibility explicitly — HF render does not always honor stacked video timing."""
    lines: list[str] = []
    for track in normalized.get("tracks", []):
        if not isinstance(track, dict):
            continue
        for clip in track.get("clips", []):
            if not isinstance(clip, dict):
                continue
            clip_id = str(clip.get("id", "")).strip()
            if not clip_id:
                continue
            start = _format_sec(clip["startSec"])
            end = _format_sec(clip["endSec"])
            selector = f"#{clip_id}"
            lines.append(f'tl.set("{selector}", {{ autoAlpha: 1 }}, {start});')
            lines.append(f'tl.set("{selector}", {{ autoAlpha: 0 }}, {end});')
            if track.get("type") == "video":
                lines.append(
                    f'tl.call(function() {{'
                    f' var node = document.querySelector("{selector}");'
                    f' if (node) try {{ node.currentTime = 0; node.play(); }} catch (_e) {{}}'
                    f' }}, [], {start});'
                )
    return "\n      ".join(lines)


def _next_track_indices(normalized: dict[str, Any]) -> dict[str, int]:
    """Assign unique data-track-index values so sequential clips do not share one HF track."""
    indices: dict[str, int] = {}
    counter = 0
    for track in normalized.get("tracks", []):
        if not isinstance(track, dict):
            continue
        for clip in track.get("clips", []):
            if not isinstance(clip, dict):
                continue
            clip_id = str(clip.get("id", "")).strip()
            if clip_id:
                indices[clip_id] = counter
                counter += 1
    return indices


def _hyperframes_attrs(
    *,
    clip_id: str,
    clip: dict[str, Any],
    track_index: int,
) -> str:
    start_sec = _format_sec(clip["startSec"])
    duration_sec = _format_sec(_clip_duration_sec(clip))
    return (
        f'id="{html.escape(clip_id)}" '
        f'data-start="{start_sec}" '
        f'data-duration="{duration_sec}" '
        f'data-track-index="{track_index}"'
    )


def _render_clip(
    track_type: str,
    clip: dict[str, Any],
    render_root: Path,
    composition_dir: Path,
    *,
    track_index: int,
) -> str:
    clip_id = str(clip.get("id", "clip-unknown"))
    attrs = _hyperframes_attrs(clip_id=clip_id, clip=clip, track_index=track_index)

    if track_type == "text":
        source_ref = str(clip.get("sourceRef", ""))
        if source_ref and _is_image_source_ref(source_ref):
            src = html.escape(_safe_asset_path(render_root, composition_dir, source_ref), quote=True)
            return f'<img class="clip image-clip" {attrs} src="{src}" alt="" />'
        if source_ref and _is_video_source_ref(source_ref):
            src = html.escape(_safe_asset_path(render_root, composition_dir, source_ref), quote=True)
            return (
                f'<video class="clip video-clip" {attrs} src="{src}" '
                f'muted playsinline preload="auto"></video>'
            )
        content = html.escape(str(clip.get("content", "")))
        return f'<div class="clip text-clip" {attrs}>{content}</div>'
    if track_type == "image":
        source_ref = str(clip.get("sourceRef", ""))
        src = html.escape(_safe_asset_path(render_root, composition_dir, source_ref), quote=True)
        return f'<img class="clip image-clip" {attrs} src="{src}" alt="" />'
    if track_type == "video":
        source_ref = str(clip.get("sourceRef", ""))
        src = html.escape(_safe_asset_path(render_root, composition_dir, source_ref), quote=True)
        return (
            f'<video class="clip video-clip" {attrs} src="{src}" '
            f'muted playsinline preload="auto"></video>'
        )
    if track_type == "effect":
        effect = html.escape(str(clip.get("content", "none")))
        return f'<div class="clip effect-clip effect-{effect}" {attrs}></div>'
    if track_type == "transition":
        name = str(clip.get("content", "fade")).strip().lower() or "fade"
        transition = name if name in {"fade", "wipe", "cut", "quick-cut"} else "fade"
        css_class = "transition-fade" if transition in {"fade", "quick-cut"} else f"transition-{transition}"
        return f'<div class="clip transition-clip {css_class}" {attrs}></div>'
    return f'<div class="clip generic-clip" {attrs}></div>'


def _write_hyperframes_json(composition_dir: Path) -> None:
    payload = {
        "$schema": "https://hyperframes.heygen.com/schema/hyperframes.json",
        "registry": "https://raw.githubusercontent.com/heygen-com/hyperframes/main/registry",
        "paths": {
            "blocks": "compositions",
            "components": "compositions/components",
            "assets": "assets",
        },
    }
    (composition_dir / "hyperframes.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def write_composition(timeline: dict[str, Any], composition_dir: Path, render_root: Path) -> None:
    composition_dir.mkdir(parents=True, exist_ok=True)
    normalized = _normalize_timeline(timeline)
    duration_sec = float(normalized.get("durationSec", 0) or 0)
    track_indices = _next_track_indices(normalized)
    gsap_script = _build_gsap_visibility_script(normalized)

    timeline_path = composition_dir / "timeline.json"
    timeline_path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_hyperframes_json(composition_dir)

    clip_nodes: list[str] = []
    for track in normalized["tracks"]:
        track_type = str(track["type"])
        for clip in track.get("clips", []):
            clip_id = str(clip.get("id", ""))
            clip_nodes.append(
                _render_clip(
                    track_type,
                    clip,
                    render_root,
                    composition_dir,
                    track_index=track_indices.get(clip_id, 0),
                )
            )

    html_doc = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width={DEFAULT_WIDTH}, height={DEFAULT_HEIGHT}" />
  <title>VideoMaker HyperFrames Composition</title>
  <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
  <style>
    * {{
      margin: 0;
      padding: 0;
      box-sizing: border-box;
    }}
    html,
    body {{
      margin: 0;
      width: {DEFAULT_WIDTH}px;
      height: {DEFAULT_HEIGHT}px;
      overflow: hidden;
      background: #0b0d12;
      color: #fff;
      font-family: Arial, sans-serif;
    }}
    #root {{
      position: relative;
      width: 100%;
      height: 100%;
      overflow: hidden;
    }}
    .clip {{
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
      object-fit: cover;
      visibility: hidden;
      opacity: 0;
    }}
    .text-clip {{
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 40px;
      text-align: center;
      padding: 48px;
    }}
    .video-clip {{
      z-index: 1;
    }}
    .image-clip {{
      z-index: 1;
    }}
    .transition-clip {{
      z-index: 2;
      pointer-events: none;
    }}
    .transition-fade {{
      background: rgba(0, 0, 0, 0.2);
    }}
  </style>
</head>
<body>
  <div
    id="root"
    data-composition-id="{COMPOSITION_ID}"
    data-start="0"
    data-duration="{_format_sec(duration_sec)}"
    data-width="{DEFAULT_WIDTH}"
    data-height="{DEFAULT_HEIGHT}"
  >
    {"".join(clip_nodes)}
  </div>
  <script>
    window.__timelines = window.__timelines || {{}};
    const tl = gsap.timeline({{ paused: true }});
    {gsap_script}
    window.__timelines["{COMPOSITION_ID}"] = tl;
    window.__videomakerTimeline = {_embed_timeline_json(normalized)};
    window.__videomakerSeek = function(ms) {{
      if (typeof window.__hyperframes !== "undefined" && window.__hyperframes.seek) {{
        window.__hyperframes.seek(ms / 1000);
        return;
      }}
      tl.seek(ms / 1000, false);
    }};
    window.__videomakerSeek(0);
  </script>
</body>
</html>
"""
    (composition_dir / "index.html").write_text(html_doc, encoding="utf-8")
