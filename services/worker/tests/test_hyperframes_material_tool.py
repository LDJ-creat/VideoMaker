from __future__ import annotations

import json
from pathlib import Path

from app.agents.material_author import run_material_author
from app.render.material_templates.scaffold import (
    MaterialScaffoldError,
    build_composition,
    sanitize_params,
    sanitize_string,
)
from app.tools.hyperframes_tool import CommandResult, HyperFramesTool
from app.tools.hyperframes_material_tool import HyperFramesMaterialTool
from app.tools.llm_tool import LLMTool

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "material_specs"


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


def test_scaffold_builds_benefit_card_composition(tmp_path: Path) -> None:
    spec = _load_fixture("benefit_card.json")
    composition_dir = build_composition(
        spec,
        tmp_path / "composition",
        project_root=tmp_path,
    )

    assert (composition_dir / "index.html").exists()
    assert (composition_dir / "hyperframes.json").exists()
    html = (composition_dir / "index.html").read_text(encoding="utf-8")
    assert "三大核心卖点" in html
    assert "轻量便携" in html
    assert 'data-composition-id="main"' in html
    assert "window.__timelines" in html


def test_scaffold_builds_title_lower_third_and_ken_burns(tmp_path: Path) -> None:
    lower_third_spec = {
        "template": "title-lower-third",
        "durationSec": 2.5,
        "params": {
            "title": "新品发布",
            "subtitle": "限时优惠",
            "colors": {"primary": "#f97316"},
        },
    }
    build_composition(
        lower_third_spec,
        tmp_path / "lower-third",
        project_root=tmp_path,
    )
    lower_html = (tmp_path / "lower-third" / "index.html").read_text(encoding="utf-8")
    assert "新品发布" in lower_html
    assert "限时优惠" in lower_html
    assert "lower-third-bar" in lower_html

    asset_root = tmp_path / "assets-root"
    asset_root.mkdir()
    image_path = asset_root / "hero.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\n")

    ken_burns_spec = {
        "template": "ken-burns",
        "durationSec": 4,
        "params": {
            "assetRefs": [
                {
                    "id": "img-1",
                    "type": "image",
                    "uri": "hero.png",
                    "createdAt": "2026-05-29T00:00:00Z",
                }
            ]
        },
    }
    build_composition(
        ken_burns_spec,
        tmp_path / "ken-burns",
        asset_root=asset_root,
        project_root=tmp_path,
    )
    copied = tmp_path / "ken-burns" / "assets" / "hero.png"
    assert copied.exists()
    ken_html = (tmp_path / "ken-burns" / "index.html").read_text(encoding="utf-8")
    assert 'src="assets/hero.png"' in ken_html
    assert "ken-burns-image" in ken_html


def test_sanitize_params_strips_injection() -> None:
    dirty = {
        "title": "<script>alert(1)</script>标题",
        "bullets": ["<b>one</b>", "javascript:alert(2)"],
    }
    cleaned = sanitize_params(dirty)
    assert "<" not in cleaned["title"]
    assert ">" not in cleaned["title"]
    assert "javascript:" not in cleaned["bullets"][1]
    assert sanitize_string("javascript:evil") == "evil"


def test_build_composition_escapes_injected_title_in_html(tmp_path: Path) -> None:
    spec = {
        "template": "benefit-card",
        "durationSec": 3,
        "params": {
            "title": "<img onerror=alert(1)>安全标题",
            "bullets": ["要点"],
            "colors": {"primary": "#2563eb"},
        },
    }
    build_composition(
        spec,
        tmp_path / "composition",
        project_root=tmp_path,
    )
    html = (tmp_path / "composition" / "index.html").read_text(encoding="utf-8")
    assert "<img onerror" not in html
    assert "安全标题" in html


def test_render_material_rejects_invalid_spec(tmp_path: Path) -> None:
    tool = HyperFramesMaterialTool()
    result = tool.render_material(
        {"template": "benefit-card"},
        project_root=tmp_path,
        output_dir=tmp_path / "composition",
        output_clip=tmp_path / "clip.mp4",
        log_path=tmp_path / "render-log.json",
    )
    assert result["ok"] is False
    assert result["error"]["code"] == "material_spec_invalid"


def test_render_material_rejects_paths_outside_project_sandbox(tmp_path: Path) -> None:
    spec = _load_fixture("benefit_card.json")
    tool = HyperFramesMaterialTool()
    project_root = tmp_path / "project"
    project_root.mkdir()

    result = tool.render_material(
        spec,
        project_root=project_root,
        output_dir=tmp_path / "outside" / "composition",
        output_clip=project_root / "generated" / "clip.mp4",
        log_path=project_root / "generated" / "render-log.json",
    )

    assert result["ok"] is False
    assert result["error"]["code"] == "material_sandbox_violation"


def test_build_composition_rejects_output_dir_outside_project_sandbox(tmp_path: Path) -> None:
    spec = _load_fixture("benefit_card.json")
    project_root = tmp_path / "project"
    project_root.mkdir()

    try:
        build_composition(
            spec,
            tmp_path / "outside" / "composition",
            project_root=project_root,
        )
    except MaterialScaffoldError as exc:
        assert "escapes project sandbox" in str(exc)
    else:
        raise AssertionError("expected sandbox violation")


def test_render_material_success_with_mocked_cli(tmp_path: Path) -> None:
    spec = _load_fixture("benefit_card.json")
    stages: list[tuple[str, str]] = []

    def runner(command: list[str], cwd: Path) -> CommandResult:
        if "render" in command:
            output_index = command.index("--output") + 1
            Path(command[output_index]).write_bytes(b"mock-mp4")
        return CommandResult(returncode=0, stdout="ok", stderr="")

    hf_tool = HyperFramesTool(command_runner=runner)
    material_tool = HyperFramesMaterialTool(
        hyperframes_tool=hf_tool,
        emit_progress=lambda stage, message: stages.append((stage, message)),
    )

    output_clip = tmp_path / "generated" / "clip.mp4"
    log_path = tmp_path / "generated" / "render-log.json"
    result = material_tool.render_material(
        spec,
        project_root=tmp_path,
        output_dir=tmp_path / "composition",
        output_clip=output_clip,
        log_path=log_path,
    )

    assert result["ok"] is True
    assert result["artifactPath"] == str(output_clip)
    assert result["durationSec"] == 3
    assert output_clip.exists()
    assert output_clip.read_bytes() == b"mock-mp4"
    assert stages == [("rendering_material", "Rendering HyperFrames material clip")]
    assert (tmp_path / "composition" / "index.html").exists()
    assert json.loads(log_path.read_text(encoding="utf-8"))["status"] == "succeeded"


def test_material_author_fixture_returns_valid_spec() -> None:
    fixture_spec = _load_fixture("benefit_card.json")
    llm = LLMTool(fixture_mode=True, fixtures={"material_author": fixture_spec})
    spec = run_material_author(
        llm,
        slot={
            "role": "benefit_card",
            "scriptIntent": "highlight product benefits",
            "visualIntent": "clean card with bullets",
        },
        brand_colors={"primary": "#2563eb"},
    )
    assert spec == fixture_spec


def test_material_author_loads_prompt_file() -> None:
    from app.agents.material_author import load_prompt

    prompt = load_prompt()
    assert "MaterialSpec" in prompt
    assert "benefit-card" in prompt
