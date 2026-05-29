from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from app.render.material_templates.scaffold import (
    MaterialScaffoldError,
    build_composition,
    ensure_paths_in_project_sandbox,
    validate_material_spec,
)
from app.tools.hyperframes_tool import HyperFramesTool

ProgressEmitter = Callable[[str, str], None]


class HyperFramesMaterialTool:
    def __init__(
        self,
        *,
        hyperframes_tool: HyperFramesTool | None = None,
        emit_progress: ProgressEmitter | None = None,
    ) -> None:
        self._hyperframes_tool = hyperframes_tool or HyperFramesTool()
        self._emit_progress = emit_progress

    def render_material(
        self,
        spec: dict[str, Any],
        *,
        project_root: Path,
        output_dir: Path,
        output_clip: Path,
        log_path: Path,
        asset_root: Path | None = None,
    ) -> dict[str, Any]:
        if self._emit_progress is not None:
            self._emit_progress("rendering_material", "Rendering HyperFrames material clip")

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

        try:
            sandbox_paths = [output_dir, output_clip, log_path]
            if asset_root is not None:
                sandbox_paths.append(asset_root)
            ensure_paths_in_project_sandbox(project_root, *sandbox_paths)
            composition_dir = build_composition(
                spec,
                output_dir,
                asset_root=asset_root,
                project_root=project_root,
            )
        except MaterialScaffoldError as exc:
            error_code = (
                "material_sandbox_violation"
                if "escapes project sandbox" in str(exc)
                else "material_scaffold_failed"
            )
            return {
                "ok": False,
                "error": {
                    "code": error_code,
                    "message": str(exc),
                    "retryable": False,
                },
            }

        output_clip.parent.mkdir(parents=True, exist_ok=True)
        render_result = self._hyperframes_tool.render(
            composition_dir=composition_dir,
            output_path=output_clip,
            log_path=log_path,
        )
        if not render_result.get("ok"):
            return render_result

        if not output_clip.exists():
            return {
                "ok": False,
                "error": {
                    "code": "material_render_missing_output",
                    "message": "HyperFrames render succeeded but output clip is missing",
                    "retryable": False,
                },
            }

        return {
            "ok": True,
            "artifactPath": str(output_clip),
            "compositionDir": str(composition_dir),
            "durationSec": float(spec["durationSec"]),
        }
