from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from app.composition.engine_factory import create_composition_engine
from app.render.material_templates.scaffold import validate_material_spec
from app.tools.hyperframes_tool import HyperFramesTool
from composition.types import RenderPaths

ProgressEmitter = Callable[[str, str], None]


class HyperFramesMaterialTool:
    def __init__(
        self,
        *,
        hyperframes_tool: HyperFramesTool | None = None,
        emit_progress: ProgressEmitter | None = None,
        composition_engine=None,
    ) -> None:
        self._hyperframes_tool = hyperframes_tool or HyperFramesTool()
        self._emit_progress = emit_progress
        self._engine = composition_engine

    def _engine_for(self):
        if self._engine is not None:
            return self._engine
        return create_composition_engine(
            hyperframes_tool=self._hyperframes_tool,
            emit_progress=self._emit_progress,
        )

    def render_material(
        self,
        spec: dict[str, Any],
        *,
        project_root: Path,
        output_dir: Path,
        output_clip: Path,
        log_path: Path,
        asset_root: Path | None = None,
        aspect_ratio: str = "9:16",
    ) -> dict[str, Any]:
        validation = validate_material_spec(spec)
        if not validation.valid:
            return {
                "ok": False,
                "error": {
                    "code": "material_spec_invalid",
                    "message": "MaterialSpec failed schema validation",
                    "retryable": False,
                    "validationErrors": [
                        {"path": item.path, "message": item.message}
                        for item in validation.errors
                    ],
                },
            }
        engine = self._engine_for()
        result = engine.render_clip(
            spec,
            RenderPaths(
                project_root=project_root,
                output_dir=output_dir,
                output_clip=output_clip,
                log_path=log_path,
                asset_root=asset_root,
                aspect_ratio=aspect_ratio,
                lint_log_path=log_path.parent / f"{log_path.stem}-lint.json",
            ),
        )
        if not result.ok:
            error = result.error or {}
            return {
                "ok": False,
                "error": {
                    "code": str(error.get("code", "material_render_failed")),
                    "message": str(error.get("message", "HyperFrames material render failed")),
                    "retryable": bool(error.get("retryable", False)),
                    **(
                        {"validationErrors": error["validationErrors"]}
                        if isinstance(error.get("validationErrors"), list)
                        else {}
                    ),
                },
            }
        return {
            "ok": True,
            "artifactPath": str(result.output_clip),
            "compositionDir": str(result.composition_dir),
            "durationSec": result.duration_sec,
            "lintPassed": result.lint_passed,
            "lintSkipped": result.lint_skipped,
            "lintLogPath": str(result.lint_log_path) if result.lint_log_path else None,
        }
