from __future__ import annotations

import json
from pathlib import Path

from composition.build.tailwind_runtime import html_uses_tailwind_classes, inject_tailwind_browser_script


def write_hyperframes_json(composition_dir: Path) -> None:
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


def write_index_html(
    *,
    composition_dir: Path,
    body_html: str,
    styles: str,
    timeline_script: str,
    duration_sec: float,
    canvas_width: int,
    canvas_height: int,
) -> None:
    html_doc = f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width={canvas_width}, height={canvas_height}" />
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
        width: {canvas_width}px;
        height: {canvas_height}px;
        overflow: hidden;
        background: #000;
      }}
      {styles}
    </style>
  </head>
  <body>
    <div
      id="root"
      data-composition-id="main"
      data-start="0"
      data-duration="{duration_sec:g}"
      data-width="{canvas_width}"
      data-height="{canvas_height}"
    >
      {body_html}
    </div>
    <script>
      window.__timelines = window.__timelines || {{}};
      const tl = gsap.timeline({{ paused: true }});
      {timeline_script}
      window.__timelines["main"] = tl;
    </script>
  </body>
</html>
"""
    if html_uses_tailwind_classes(body_html) or html_uses_tailwind_classes(styles):
        html_doc = inject_tailwind_browser_script(html_doc)
    (composition_dir / "index.html").write_text(html_doc, encoding="utf-8")
