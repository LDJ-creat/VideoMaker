from __future__ import annotations

import json
from pathlib import Path

from app.render.backend import RenderOptions
from app.render.hyperframes_backend import HyperFramesRenderBackend


class MissingTool:
    def render(self, composition_dir: Path, output_path: Path, log_path: Path) -> dict:
        log_path.write_text(
            json.dumps({"status": "missing_cli", "command": ["npx", "hyperframes"]}),
            encoding="utf-8",
        )
        return {
            "ok": False,
            "error": {
                "code": "hyperframes_missing",
                "message": "missing",
                "retryable": True,
            },
        }


class SuccessTool:
    def render(self, composition_dir: Path, output_path: Path, log_path: Path) -> dict:
        output_path.write_text("mp4", encoding="utf-8")
        log_path.write_text(
            json.dumps({"status": "succeeded", "command": ["npx", "hyperframes"]}),
            encoding="utf-8",
        )
        return {"ok": True}


def _timeline() -> dict:
    return {
        "durationSec": 2,
        "tracks": [
            {
                "id": "text",
                "type": "text",
                "clips": [{"id": "t1", "startSec": 0, "endSec": 2, "content": "Hello <b>world</b>"}],
            }
        ],
    }


def test_backend_keeps_preview_artifacts_when_cli_missing(tmp_path: Path) -> None:
    stages: list[str] = []
    backend = HyperFramesRenderBackend(tool=MissingTool())
    options = RenderOptions(
        project_id="proj-1",
        generation_id="gen-1",
        timeline=_timeline(),
        storage_root=tmp_path,
        emit_progress=stages.append,
    )

    output = backend.render(options)

    assert output.error is not None
    assert output.error["retryable"] is True
    assert any(artifact["uri"].endswith("preview.html") for artifact in output.artifact_refs)
    assert stages == ["building_timeline", "rendering", "completed"]
    preview_path = tmp_path / "projects" / "proj-1" / "renders" / "gen-1" / "preview.html"
    assert preview_path.exists()


def test_backend_returns_mp4_artifact_when_render_succeeds(tmp_path: Path) -> None:
    backend = HyperFramesRenderBackend(tool=SuccessTool())
    options = RenderOptions(
        project_id="proj-1",
        generation_id="gen-1",
        timeline=_timeline(),
        storage_root=tmp_path,
    )

    output = backend.render(options)
    mp4_artifacts = [a for a in output.artifact_refs if a["uri"].endswith("output.mp4")]
    assert output.error is None
    assert len(mp4_artifacts) == 1
