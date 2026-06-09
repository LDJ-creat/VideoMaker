from __future__ import annotations

import json
from pathlib import Path

import pytest

from composition.patterns.deposit import deposit_pattern_candidate, promote_pattern
from composition.patterns.promote_prepare import PromotePrepareContext, prepare_promoted_pattern_bundle
from composition.patterns.sanitize import sanitize_instance_spec
from composition.patterns.deposit import PromoteRejected, PatternPromoteRequest, PatternDepositContext
from composition.render.hyperframes_cli import HyperFramesCli, fixture_command_runner


def test_sanitize_replaces_storyboard_literals() -> None:
    spec = {
        "template": "composition",
        "durationSec": 2,
        "composition": {
            "bodyHtml": "<div>限时特惠三天见效</div>",
            "timelineScript": "tl.set('.x', {}, 0);",
        },
    }
    scene = {"scriptIntent": "限时特惠三天见效", "visualIntent": "产品特写"}
    sanitized = sanitize_instance_spec(spec, scene=scene)
    assert "{{title}}" in sanitized["composition"]["bodyHtml"]
    assert "限时特惠" not in sanitized["composition"]["bodyHtml"]


def test_prepare_and_promote_pattern(tmp_path: Path) -> None:
    storage = tmp_path / "storage"
    spec = {
        "template": "composition",
        "durationSec": 2,
        "composition": {"bodyHtml": '<div id="root">卖点文案</div>'},
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
    gen_root = storage / "projects" / "p1" / "generations" / "g1"
    gen_root.mkdir(parents=True, exist_ok=True)
    (gen_root / "generation-plan.json").write_text(
        json.dumps(
            {
                "storyboard": [
                    {
                        "slotId": "slot-1",
                        "role": "benefit_card",
                        "scriptIntent": "卖点文案",
                        "visualIntent": "卡片展示",
                    }
                ],
                "completionActions": [
                    {
                        "id": "action-slot-1",
                        "slotId": "slot-1",
                        "provider": "hyperframes_material",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    def author_fn(**kwargs):
        material = kwargs["material_spec"]
        return {
            "frontmatter": {
                "title": "Test Pattern",
                "category": "composition",
                "summary": "测试动效",
                "slotRoles": ["benefit_card"],
                "motionPattern": "fade-in",
            },
            "markdown": "## 适用场景\n\n测试\n\n## 动效模式\n\nfade\n\n## 占位符约定\n\n{{title}}\n\n## 适用 role\n\nbenefit_card\n\n## 迁移注意\n\nnone",
            "materialSpec": material,
        }

    prepare_promoted_pattern_bundle(
        PromotePrepareContext(
            storage_root=storage,
            project_id="p1",
            generation_id="g1",
            slot_id="slot-1",
        ),
        author_fn=author_fn,
        hyperframes_cli=HyperFramesCli(command_runner=fixture_command_runner()),
        repo_root=tmp_path,
    )
    published = promote_pattern(
        PatternPromoteRequest(
            storage_root=storage,
            project_id="p1",
            generation_id="g1",
            slot_id="slot-1",
        ),
    )
    published_dir = Path(published["publishedDir"])
    assert (published_dir / "spec.template.json").is_file()
    assert (published_dir / "spec.instance.json").is_file()
    assert (published_dir / "composition-skill.md").is_file()


def test_promote_requires_prepared_bundle(tmp_path: Path) -> None:
    storage = tmp_path / "storage"
    spec = {
        "template": "composition",
        "durationSec": 2,
        "composition": {"bodyHtml": '<div id="root">x</div>'},
    }
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
            composition_dir=tmp_path / "comp",
            lint_passed=True,
            render_passed=True,
            lint_log_path=lint_log,
        )
    )
    with pytest.raises(PromoteRejected, match="prepared_bundle_missing"):
        promote_pattern(
            PatternPromoteRequest(
                storage_root=storage,
                project_id="p1",
                generation_id="g1",
                slot_id="slot-1",
            ),
        )
