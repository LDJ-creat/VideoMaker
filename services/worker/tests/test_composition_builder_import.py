from __future__ import annotations

from pathlib import Path


def test_composition_builder_exposes_install_registry_blocks() -> None:
    from composition.build import composition_builder as module

    assert callable(module.install_registry_blocks)


def test_build_composition_template_with_registry_blocks(tmp_path: Path) -> None:
    from composition.build.composition_builder import build_composition

    spec = {
        "template": "composition",
        "durationSec": 2,
        "composition": {
            "bodyHtml": '<div id="root">x</div>',
            "registryBlocks": ["caption-style-minimal"],
        },
    }
    out = build_composition(spec, tmp_path / "comp", project_root=tmp_path)
    assert (out / "index.html").is_file()
