from __future__ import annotations

import json
from pathlib import Path

import pytest

from composition.author.tools import CompositionToolExecutor
from composition.material_review.session import write_review_marker
from composition.skills.runtime import SkillRuntime
from composition.types import BuildContext


def _build_executor(tmp_path: Path, repo_root: Path) -> CompositionToolExecutor:
    build_ctx = BuildContext(
        project_root=repo_root,
        output_dir=tmp_path,
        aspect_ratio="9:16",
        asset_root=None,
    )
    return CompositionToolExecutor(
        skill_runtime=SkillRuntime(repo_root=repo_root, storage_root=tmp_path),
        build_ctx=build_ctx,
        lint_root=tmp_path,
        repo_root=repo_root,
        author_payload={},
    )


def test_submit_material_spec_rejects_without_review_marker(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIDEOMAKER_MATERIAL_REVIEW_ENABLED", "true")
    repo_root = Path(__file__).resolve().parents[3]
    executor = _build_executor(tmp_path, repo_root)
    spec = {"template": "benefit-card", "durationSec": 3, "params": {"title": "A", "bullets": []}}
    payload = json.loads(
        executor.execute(
            "submit_material_spec",
            {"spec_json": spec},
        )
    )
    assert payload["accepted"] is False
    assert "review_material_preview" in payload["error"]


def test_submit_material_spec_rejects_mutated_spec_after_review(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIDEOMAKER_MATERIAL_REVIEW_ENABLED", "true")
    repo_root = Path(__file__).resolve().parents[3]
    executor = _build_executor(tmp_path, repo_root)
    spec = {"template": "benefit-card", "durationSec": 3, "params": {"title": "A", "bullets": []}}
    write_review_marker(
        tmp_path,
        spec=spec,
        report={"approved": True, "issues": [], "suggestions": []},
    )
    ok_payload = json.loads(
        executor.execute(
            "submit_material_spec",
            {"spec_json": spec},
        )
    )
    assert ok_payload["accepted"] is True

    mutated = {**spec, "durationSec": 4}
    submit_payload = json.loads(
        executor.execute(
            "submit_material_spec",
            {"spec_json": mutated},
        )
    )
    assert submit_payload["accepted"] is False
    assert "does not match" in submit_payload["error"]
