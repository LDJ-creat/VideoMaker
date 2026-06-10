from __future__ import annotations

import pytest

from composition.paths import detect_repo_root
from composition.skills.bootstrap import build_bootstrap_system_prompt
from composition.skills.runtime import SkillRuntime


@pytest.fixture()
def repo_root():
    return detect_repo_root()


def test_bootstrap_prompt_lists_visual_craft_skill(repo_root) -> None:
    prompt = build_bootstrap_system_prompt(repo_root=repo_root)
    assert "videomaker-visual-craft" in prompt
    assert "skills/private/videomaker-visual-craft/SKILL.md" in prompt
    assert "visualStyleBible.avoid" in prompt
    assert "house-style" in prompt


def test_visual_craft_references_are_readable(repo_root) -> None:
    runtime = SkillRuntime(repo_root=repo_root)
    for rel in (
        "skills/private/videomaker-visual-craft/references/ANTI-AI-FINGERPRINTS.md",
        "skills/private/videomaker-visual-craft/references/SLOT-VISUAL-CRAFT.md",
        "skills/private/videomaker-visual-craft/references/MOTION-BY-CONTENT.md",
        "skills/private/videomaker-visual-craft/references/PALETTE-FROM-BIBLE.md",
    ):
        content = runtime.skill_view(rel)
        assert len(content) > 100
