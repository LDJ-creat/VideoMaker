from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

TRACK_ORDER = {
    "video": 0,
    "image": 1,
    "text": 2,
    "effect": 3,
    "transition": 4,
    "voiceover": 5,
    "bgm": 6,
}


def _to_ms(seconds: float) -> int:
    return round(float(seconds) * 1000)


def _safe_asset_path(render_root: Path, composition_dir: Path, source_ref: str) -> str:
    candidate = (render_root / source_ref).resolve()
    root = render_root.resolve()
    if not candidate.is_relative_to(root):
        raise ValueError("sourceRef escapes render directory")
    return candidate.relative_to(root).as_posix()


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


def _render_clip(track_type: str, clip: dict[str, Any], render_root: Path, composition_dir: Path) -> str:
    start_ms = _to_ms(clip["startSec"])
    end_ms = _to_ms(clip["endSec"])
    attrs = (
        f'data-track="{html.escape(track_type)}" '
        f'data-start-ms="{start_ms}" '
        f'data-end-ms="{end_ms}"'
    )

    if track_type == "text":
        content = html.escape(str(clip.get("content", "")))
        return f'<div class="clip text-clip" {attrs}>{content}</div>'
    if track_type == "image":
        source_ref = str(clip.get("sourceRef", ""))
        src = html.escape(_safe_asset_path(render_root, composition_dir, source_ref), quote=True)
        return f'<img class="clip image-clip" {attrs} src="{src}" alt="" />'
    if track_type == "video":
        source_ref = str(clip.get("sourceRef", ""))
        src = html.escape(_safe_asset_path(render_root, composition_dir, source_ref), quote=True)
        return f'<video class="clip video-clip" {attrs} src="{src}" muted preload="auto"></video>'
    if track_type == "effect":
        effect = html.escape(str(clip.get("content", "none")))
        return f'<div class="clip effect-clip effect-{effect}" {attrs}></div>'
    if track_type == "transition":
        name = str(clip.get("content", "fade")).strip().lower() or "fade"
        transition = name if name in {"fade", "wipe", "cut"} else "fade"
        return f'<div class="clip transition-clip transition-{html.escape(transition)}" {attrs}></div>'
    return f'<div class="clip generic-clip" {attrs}></div>'


def write_composition(timeline: dict[str, Any], composition_dir: Path, render_root: Path) -> None:
    composition_dir.mkdir(parents=True, exist_ok=True)
    normalized = _normalize_timeline(timeline)

    timeline_path = composition_dir / "timeline.json"
    timeline_path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")

    clip_nodes: list[str] = []
    for track in normalized["tracks"]:
        track_type = str(track["type"])
        for clip in track.get("clips", []):
            clip_nodes.append(_render_clip(track_type, clip, render_root, composition_dir))

    html_doc = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>VideoMaker HyperFrames Preview</title>
  <style>
    body {{ margin: 0; background: #0b0d12; color: #fff; font-family: Arial, sans-serif; }}
    #stage {{ position: relative; width: 100vw; height: 100vh; overflow: hidden; }}
    .clip {{ position: absolute; inset: 0; display: none; }}
    .clip.is-active {{ display: block; }}
    .text-clip {{ display: none; align-items: center; justify-content: center; font-size: 40px; text-align: center; }}
    .text-clip.is-active {{ display: flex; }}
    .transition-fade {{ background: rgba(0, 0, 0, 0.2); }}
  </style>
</head>
<body>
  <div id="stage">
    {"".join(clip_nodes)}
  </div>
  <script>
    window.__videomakerTimeline = {json.dumps(normalized, ensure_ascii=False)};
    window.__videomakerSeek = function(ms) {{
      var nodes = document.querySelectorAll(".clip");
      nodes.forEach(function(node) {{
        var start = Number(node.dataset.startMs || "0");
        var end = Number(node.dataset.endMs || "0");
        var active = ms >= start && ms < end;
        node.classList.toggle("is-active", active);
        if (active && node.tagName === "VIDEO") {{
          var localSec = Math.max(0, (ms - start) / 1000);
          try {{ node.currentTime = localSec; }} catch (_e) {{}}
        }}
      }});
    }};
    window.__videomakerSeek(0);
  </script>
</body>
</html>
"""
    (composition_dir / "index.html").write_text(html_doc, encoding="utf-8")
