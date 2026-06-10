from __future__ import annotations

from composition.skills.usage_requirements import (
    REQUIRED_PRIVATE_SKILL_PATHS,
    REQUIRED_VISUAL_CRAFT_REFERENCE_PATHS,
    VISUAL_BIBLE_EXTRA_READ_PATHS,
    record_skill_view,
    skill_view_requirement_error,
    visual_craft_bootstrap_section,
)


def test_skill_view_requirement_error_requires_private_skills() -> None:
    viewed: set[str] = set()
    error = skill_view_requirement_error(viewed, has_visual_style_bible=False)
    assert error is not None
    assert REQUIRED_PRIVATE_SKILL_PATHS[0] in error


def test_skill_view_requirement_error_passes_when_minimum_reads_done() -> None:
    viewed: set[str] = set()
    for path in (
        *REQUIRED_PRIVATE_SKILL_PATHS,
        *REQUIRED_VISUAL_CRAFT_REFERENCE_PATHS,
    ):
        record_skill_view(viewed, path)
    assert skill_view_requirement_error(viewed, has_visual_style_bible=False) is None


def test_skill_view_requirement_error_requires_palette_when_bible_present() -> None:
    viewed: set[str] = set()
    for path in (
        *REQUIRED_PRIVATE_SKILL_PATHS,
        *REQUIRED_VISUAL_CRAFT_REFERENCE_PATHS,
    ):
        record_skill_view(viewed, path)
    error = skill_view_requirement_error(viewed, has_visual_style_bible=True)
    assert error is not None
    assert VISUAL_BIBLE_EXTRA_READ_PATHS[0] in error


def test_bootstrap_includes_copy_policy_rules() -> None:
    section = visual_craft_bootstrap_section()
    assert "Voiceover text must not appear in composition DOM" in section
    assert "Brief fields" in section
