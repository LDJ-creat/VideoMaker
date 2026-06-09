from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.render.backend import RenderBackend, RenderOptions, RenderOutput
from app.render.composition_preview import build_composition_preview
from app.tools.hyperframes_tool import HyperFramesTool
from video.poster import extract_video_poster


def _artifact_ref(artifact_type: str, uri: str) -> dict[str, Any]:
    return {
        "id": str(uuid4()),
        "type": artifact_type,
        "uri": uri.replace("\\", "/"),
        "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


class HyperFramesRenderBackend(RenderBackend):
    def __init__(self, tool: Any | None = None) -> None:
        self._tool = tool or HyperFramesTool()

    def render(self, options: RenderOptions) -> RenderOutput:
        options.emit_progress("building_timeline")
        preview = build_composition_preview(options)

        options.emit_progress("rendering")
        output_path = preview.render_root / "output.mp4"
        log_path = preview.render_root / "render-log.json"
        tool_result = self._tool.render(
            composition_dir=preview.composition_dir,
            output_path=output_path,
            log_path=log_path,
        )

        artifact_refs = [
            _artifact_ref("html", str(preview.preview_path)),
            _artifact_ref("html", str(preview.composition_dir / "index.html")),
            _artifact_ref("json", str(preview.timeline_json_path)),
            _artifact_ref("json", str(log_path)),
        ]
        if tool_result.get("ok") and output_path.exists():
            artifact_refs.append(_artifact_ref("video", str(output_path)))
            if output_path.stat().st_size > 0:
                extract_video_poster(output_path, preview.render_root / "poster.jpg")

        options.emit_progress("completed")
        return RenderOutput(
            artifact_refs=artifact_refs,
            error=tool_result.get("error"),
        )
