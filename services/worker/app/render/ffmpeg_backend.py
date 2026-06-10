from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.render.backend import RenderBackend, RenderOptions, RenderOutput
from app.render.composition_preview import build_composition_preview
from app.render.timeline_compiler.compile import compile_timeline_to_mp4
from app.tools.ffmpeg_tool import FFmpegTool
from video.poster import extract_video_poster


def _artifact_ref(artifact_type: str, uri: str) -> dict[str, Any]:
    return {
        "id": str(uuid4()),
        "type": artifact_type,
        "uri": uri.replace("\\", "/"),
        "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


class FfmpegRenderBackend(RenderBackend):
    def __init__(self, tool: FFmpegTool | None = None) -> None:
        self._tool = tool or FFmpegTool()

    def render(self, options: RenderOptions) -> RenderOutput:
        started = time.perf_counter()
        options.emit_progress("building_timeline")
        preview = build_composition_preview(options)

        options.emit_progress("compiling_timeline")
        output_path = preview.render_root / "output.mp4"
        log_path = preview.render_root / "render-log.json"

        def compile_progress(stage: str) -> None:
            options.emit_progress(f"rendering_{stage}")

        compile_result = compile_timeline_to_mp4(
            options.timeline,
            render_root=preview.render_root,
            output_path=output_path,
            aspect_ratio=options.aspect_ratio,
            ffmpeg=self._tool,
            tts_mode=options.tts_mode,
            emit_progress=compile_progress,
        )

        log = dict(compile_result.log)
        log["backend"] = "ffmpeg"
        log.setdefault("durationMs", round((time.perf_counter() - started) * 1000))
        if compile_result.error:
            log["error"] = compile_result.error
        log_path.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")

        artifact_refs = [
            _artifact_ref("html", str(preview.preview_path)),
            _artifact_ref("html", str(preview.composition_dir / "index.html")),
            _artifact_ref("json", str(preview.timeline_json_path)),
            _artifact_ref("json", str(log_path)),
        ]

        if not compile_result.ok:
            options.emit_progress("completed")
            return RenderOutput(artifact_refs=artifact_refs, error=compile_result.error)

        options.emit_progress("rendering")
        if compile_result.output_path and compile_result.output_path.exists():
            artifact_refs.append(_artifact_ref("video", str(compile_result.output_path)))
            if compile_result.output_path.stat().st_size > 0:
                extract_video_poster(
                    compile_result.output_path,
                    preview.render_root / "poster.jpg",
                )

        options.emit_progress("completed")
        return RenderOutput(artifact_refs=artifact_refs)
