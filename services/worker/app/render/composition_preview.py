from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.render.backend import RenderOptions
from app.render.render_timeline_to_hyperframes import write_composition


@dataclass(slots=True)
class CompositionPreviewArtifacts:
    render_root: Path
    composition_dir: Path
    preview_path: Path
    timeline_json_path: Path


def build_composition_preview(options: RenderOptions) -> CompositionPreviewArtifacts:
    """Write HyperFrames-style HTML composition + preview iframe wrapper."""
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
    return CompositionPreviewArtifacts(
        render_root=render_root,
        composition_dir=composition_dir,
        preview_path=preview_path,
        timeline_json_path=composition_dir / "timeline.json",
    )
