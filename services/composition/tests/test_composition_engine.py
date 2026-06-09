from __future__ import annotations

import json
from pathlib import Path

import pytest

from composition.api import CompositionEngine
from composition.build.composition_builder import build_composition
from composition.build.html_safety import HtmlSafetyError, validate_composition_fragment
from composition.patterns.deposit import PromoteRejected, deposit_pattern_candidate, promote_pattern
from composition.patterns.resolver import pattern_l0_cards
from composition.registry.installer import filter_registry_block_ids, install_registry_blocks
from composition.render.hyperframes_cli import HyperFramesCli, fixture_command_runner
from composition.skills.catalog import SkillCatalog
from composition.skills.runtime import SkillRuntime
from composition.types import AuthorRequest, PatternDepositContext, PatternPromoteRequest, RenderPaths


def test_skill_catalog_uses_trigger_descriptions() -> None:
    catalog = SkillCatalog()
    entries = {entry.name: entry.description for entry in catalog.list_entries()}
    assert "hyperframes" in entries
    assert "触发" in entries["hyperframes"]


def test_skill_view_reads_private_skill(repo_root: Path) -> None:
    runtime = SkillRuntime(repo_root=repo_root)
    content = runtime.skill_view("skills/private/videomaker-composition/SKILL.md")
    assert "MaterialSpec" in content


def test_html_safety_rejects_doctype() -> None:
    with pytest.raises(HtmlSafetyError):
        validate_composition_fragment(
            body_html="<!doctype html><html><body>x</body></html>",
        )


def test_registry_blocks_rejects_unknown_ids() -> None:
    accepted, rejected = filter_registry_block_ids(["caption-style-minimal", "evil-block"])
    assert "caption-style-minimal" in accepted
    assert "evil-block" in rejected


def test_build_composition_rejects_unknown_registry_block(tmp_path: Path) -> None:
    spec = {
        "template": "composition",
        "durationSec": 2,
        "composition": {
            "bodyHtml": '<div id="root">x</div>',
            "registryBlocks": ["not-a-real-block"],
        },
    }
    with pytest.raises(Exception, match="Unknown registryBlocks"):
        build_composition(spec, tmp_path / "comp", project_root=tmp_path)


def test_build_composition_template(tmp_path: Path) -> None:
    spec = {
        "template": "composition",
        "durationSec": 2,
        "composition": {
            "bodyHtml": '<div id="root" class="card">Hello</div>',
            "styles": ".card { opacity: 0; }",
            "timelineScript": 'tl.set("#root", { autoAlpha: 1 }, 0);',
        },
    }
    out = build_composition(spec, tmp_path / "comp", project_root=tmp_path)
    assert "Hello" in (out / "index.html").read_text(encoding="utf-8")


def test_engine_render_fixture(tmp_path: Path, repo_root: Path) -> None:
    spec = {
        "template": "benefit-card",
        "durationSec": 3,
        "params": {"title": "测试", "bullets": ["一点"], "colors": {"primary": "#2563eb"}},
    }
    engine = CompositionEngine(
        hyperframes_cli=HyperFramesCli(command_runner=fixture_command_runner(), repo_root=repo_root),
    )
    clip = tmp_path / "clip.mp4"
    lint_log = tmp_path / "render-log-lint.json"
    lint_log.write_text(json.dumps({"ok": True}), encoding="utf-8")
    result = engine.render_clip(
        spec,
        RenderPaths(
            project_root=tmp_path,
            output_dir=tmp_path / "composition",
            output_clip=clip,
            log_path=tmp_path / "render-log.json",
            lint_log_path=lint_log,
        ),
    )
    assert result.ok
    assert result.lint_passed is True
    assert clip.exists()


def test_deposit_requires_lint_log_ok(tmp_path: Path) -> None:
    storage = tmp_path / "storage"
    spec = {"template": "composition", "durationSec": 2, "composition": {"bodyHtml": '<div id="root">x</div>'}}
    bad_log = tmp_path / "bad-lint.json"
    bad_log.write_text(json.dumps({"ok": False, "errors": ["fail"]}), encoding="utf-8")
    with pytest.raises(ValueError, match="lint log"):
        deposit_pattern_candidate(
            PatternDepositContext(
                storage_root=storage,
                project_id="p1",
                generation_id="g1",
                slot_id="slot-1",
                slot_role="benefit_card",
                spec=spec,
                composition_dir=tmp_path / "comp",
                lint_passed=True,
                render_passed=True,
                lint_log_path=bad_log,
            )
        )


def test_deposit_and_promote_pattern(tmp_path: Path) -> None:
    storage = tmp_path / "storage"
    spec = {
        "template": "composition",
        "durationSec": 2,
        "composition": {"bodyHtml": '<div id="root">x</div>'},
    }
    comp_dir = tmp_path / "comp"
    comp_dir.mkdir()
    lint_log = tmp_path / "lint-log.json"
    lint_log.write_text(json.dumps({"ok": True}), encoding="utf-8")
    deposit_pattern_candidate(
        PatternDepositContext(
            storage_root=storage,
            project_id="p1",
            generation_id="g1",
            slot_id="slot-1",
            slot_role="benefit_card",
            spec=spec,
            composition_dir=comp_dir,
            lint_passed=True,
            render_passed=True,
            lint_log_path=lint_log,
        )
    )
    draft = storage / "projects/p1/knowledge/drafts/composition/g1/slot-1"
    assert (draft / "lint-log.json").is_file()
    meta = json.loads((draft / "entry-meta.json").read_text(encoding="utf-8"))
    assert meta["slotRoles"] == ["benefit_card"]

    with pytest.raises(PromoteRejected):
        promote_pattern(
            PatternPromoteRequest(
                storage_root=storage,
                project_id="p1",
                generation_id="g1",
                slot_id="slot-1",
                user_score=3,
            ),
            hyperframes_cli=HyperFramesCli(command_runner=fixture_command_runner()),
        )
    published = promote_pattern(
        PatternPromoteRequest(
            storage_root=storage,
            project_id="p1",
            generation_id="g1",
            slot_id="slot-1",
            user_score=4,
            title="Test Pattern",
        ),
        hyperframes_cli=HyperFramesCli(command_runner=fixture_command_runner()),
    )
    assert published["entryKind"] == "composition_pattern"


def test_pattern_l0_includes_published_knowledge(tmp_path: Path) -> None:
    storage = tmp_path / "storage"
    entry_dir = storage / "knowledge" / "motion" / "pat-1"
    entry_dir.mkdir(parents=True)
    (entry_dir / "composition-skill.md").write_text("# pattern", encoding="utf-8")
    (entry_dir / "spec.template.json").write_text("{}", encoding="utf-8")
    (entry_dir / "entry-meta.json").write_text(
        json.dumps({"entryKind": "composition_pattern", "title": "Kinetic Card", "slotRoles": ["benefit_card"]}),
        encoding="utf-8",
    )
    cards = pattern_l0_cards(storage, project_id="p1", slot_role="benefit_card")
    assert len(cards) == 1
    assert cards[0]["source"] == "published"


def test_author_fixture_spec() -> None:
    engine = CompositionEngine.fixture(
        fixture_spec={"template": "benefit-card", "durationSec": 3, "params": {"title": "fixture"}},
    )
    spec = engine.author_material_spec(
        AuthorRequest(project_id="p1", slot={"role": "benefit_card", "scriptIntent": "x", "visualIntent": "y"})
    )
    assert spec["template"] == "benefit-card"


@pytest.fixture
def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]
