from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from app.render.backend import RenderOptions, RenderOutput


def test_render_output_is_json_friendly(tmp_path: Path) -> None:
    output = RenderOutput(
        artifact_refs=[
            {
                "id": "preview",
                "type": "html",
                "uri": "storage/projects/p1/renders/g1/preview.html",
                "createdAt": "2026-05-28T00:00:00Z",
            }
        ],
        error=None,
    )

    payload = asdict(output)
    assert payload["artifact_refs"][0]["type"] == "html"
    assert payload["error"] is None


def test_render_options_accepts_progress_callback(tmp_path: Path) -> None:
    stages: list[str] = []

    def emit(stage: str) -> None:
        stages.append(stage)

    options = RenderOptions(
        project_id="proj-1",
        generation_id="gen-1",
        timeline={"durationSec": 1, "tracks": []},
        storage_root=tmp_path,
        emit_progress=emit,
    )

    options.emit_progress("building_timeline")
    assert stages == ["building_timeline"]
