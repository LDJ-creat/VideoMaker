from __future__ import annotations

import json
from pathlib import Path

import pytest

from composition.author.tools import CompositionToolExecutor
from composition.skills.runtime import SkillRuntime
from composition.types import BuildContext


@pytest.fixture
def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def test_skill_view_returns_json_error_for_missing_file(repo_root: Path, tmp_path: Path) -> None:
    runtime = SkillRuntime(repo_root=repo_root, storage_root=tmp_path)
    executor = CompositionToolExecutor(
        skill_runtime=runtime,
        build_ctx=BuildContext(
            project_root=repo_root,
            output_dir=tmp_path,
            asset_root=None,
            aspect_ratio="9:16",
        ),
        lint_root=tmp_path,
        repo_root=repo_root,
    )

    observation = executor.execute(
        "skill_view",
        {"location": "projects/missing/knowledge/drafts/composition/gen/slot-1/composition-skill.md"},
    )
    payload = json.loads(observation)
    assert payload["ok"] is False
    assert "skill file not found" in payload["error"]
