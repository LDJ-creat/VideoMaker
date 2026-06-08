from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.render.backend import RenderBackend, RenderOptions, RenderOutput
from app.render.render_timeline_to_hyperframes import write_composition
from app.tools.hyperframes_tool import HyperFramesTool


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
        render_root = (
            Path(options.storage_root)
            / "projects"
            / options.project_id
            / "renders"
            / options.generation_id
        )
        composition_dir = render_root / "composition"
        write_composition(
            timeline=options.timeline,
            composition_dir=composition_dir,
            render_root=render_root,
            aspect_ratio=options.aspect_ratio,
        )

        preview_path = render_root / "preview.html"
        preview_path.parent.mkdir(parents=True, exist_ok=True)
        preview_path.write_text(
            '<!doctype html><html><body style="margin:0;"><iframe src="composition/index.html" '
            'style="border:0;width:100vw;height:100vh;"></iframe></body></html>',
            encoding="utf-8",
        )

        options.emit_progress("rendering")
        output_path = render_root / "output.mp4"
        log_path = render_root / "render-log.json"
        tool_result = self._tool.render(
            composition_dir=composition_dir,
            output_path=output_path,
            log_path=log_path,
        )

        artifact_refs = [
            _artifact_ref("html", str(preview_path)),
            _artifact_ref("html", str(composition_dir / "index.html")),
            _artifact_ref("json", str(composition_dir / "timeline.json")),
            _artifact_ref("json", str(log_path)),
        ]
        if tool_result.get("ok") and output_path.exists():
            artifact_refs.append(_artifact_ref("video", str(output_path)))

        options.emit_progress("completed")
        return RenderOutput(
            artifact_refs=artifact_refs,
            error=tool_result.get("error"),
        )
