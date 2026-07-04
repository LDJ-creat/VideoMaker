from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from composition.lint_pipeline import (
    LintContext,
    build_and_lint_spec,
    compute_spec_content_hash,
    lint_material_spec_full,
    lint_passed_for_hash,
    record_lint_passed,
    validate_spec_gate,
)
from composition.render.hyperframes_cli import fixture_command_runner, HyperFramesCli


@pytest.fixture
def lint_ctx(tmp_path: Path) -> LintContext:
    return LintContext(
        scratch_dir=tmp_path / "scratch",
        repo_root=tmp_path,
        author_payload={"slot": {"role": "benefit_card"}},
        aspect_ratio="9:16",
    )


def _benefit_spec() -> dict:
    return {
        "template": "benefit-card",
        "durationSec": 3,
        "params": {
            "title": "Test",
            "bullets": ["One"],
            "colors": {"primary": "#2563eb", "background": "#0f172a", "text": "#ffffff"},
        },
    }


def test_validate_spec_gate_rejects_invalid_template(lint_ctx: LintContext) -> None:
    errors = validate_spec_gate({"durationSec": 3}, lint_ctx.author_payload)
    assert errors


def test_compute_spec_content_hash_stable(lint_ctx: LintContext) -> None:
    spec = _benefit_spec()
    first = compute_spec_content_hash(spec, lint_ctx)
    second = compute_spec_content_hash(spec, lint_ctx)
    assert first == second


def test_schema_only_skips_build(lint_ctx: LintContext, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VM_ACP_FIXTURE_LINT", "1")
    errors, result = lint_material_spec_full(_benefit_spec(), lint_ctx, schema_only=True)
    assert errors == []
    assert result is not None
    assert result.ok is True
    assert not (lint_ctx.scratch_dir / "lint-draft" / "index.html").exists()


def test_build_and_lint_fixture(lint_ctx: LintContext, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VM_ACP_FIXTURE_LINT", "1")
    lint_ctx.scratch_dir.mkdir(parents=True, exist_ok=True)
    result = build_and_lint_spec(
        _benefit_spec(),
        lint_ctx,
        cli=HyperFramesCli(command_runner=fixture_command_runner(), repo_root=lint_ctx.repo_root),
    )
    assert result.ok is True
    assert result.draft_dir is not None
    assert (result.draft_dir / "index.html").is_file()


def test_skip_hf_if_cached(lint_ctx: LintContext, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VM_ACP_FIXTURE_LINT", "1")
    monkeypatch.setenv("VIDEOMAKER_COMPOSITION_LINT_CACHE", "true")
    lint_ctx.scratch_dir.mkdir(parents=True, exist_ok=True)
    spec = _benefit_spec()
    cli = HyperFramesCli(command_runner=fixture_command_runner(), repo_root=lint_ctx.repo_root)
    first = build_and_lint_spec(spec, lint_ctx, cli=cli)
    assert first.ok is True
    spec_hash = compute_spec_content_hash(spec, lint_ctx)
    assert lint_passed_for_hash(lint_ctx, spec_hash)

    errors, second = lint_material_spec_full(spec, lint_ctx, skip_hf_if_cached=True, cli=cli)
    assert errors == []
    assert second is not None
    assert second.cached is True


def test_lint_cache_disabled(lint_ctx: LintContext, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIDEOMAKER_COMPOSITION_LINT_CACHE", "false")
    spec_hash = "abc"
    record_lint_passed(
        lint_ctx,
        spec_hash=spec_hash,
        draft_dir=lint_ctx.scratch_dir / "lint-draft",
        hyperframes_command=["hyperframes"],
    )
    assert lint_passed_for_hash(lint_ctx, spec_hash) is False


def test_record_lint_passed_writes_json(lint_ctx: LintContext) -> None:
    lint_ctx.scratch_dir.mkdir(parents=True, exist_ok=True)
    draft = lint_ctx.scratch_dir / "lint-draft"
    draft.mkdir(parents=True, exist_ok=True)
    (draft / "index.html").write_text("<div></div>", encoding="utf-8")
    record_lint_passed(
        lint_ctx,
        spec_hash="deadbeef",
        draft_dir=draft,
        hyperframes_command=["hyperframes", "lint"],
    )
    payload = json.loads((lint_ctx.scratch_dir / "lint-draft" / ".lint-passed.json").read_text(encoding="utf-8"))
    assert payload["specHash"] == "deadbeef"
