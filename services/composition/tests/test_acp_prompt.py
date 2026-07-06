from __future__ import annotations

from composition.skills.acp_prompt import build_acp_author_system_prompt


def test_acp_prompt_contains_stop_rules_and_display_copy_tree() -> None:
    prompt = build_acp_author_system_prompt(template_mode="composition")
    assert "L0 STOP RULES" in prompt
    assert "displayCopy IF allowedDisplayCopy" in prompt
    assert "VM_ACP_FIXTURE_LINT" in prompt
    assert "visual_craft_bootstrap_section" not in prompt
    assert "<available_skills>" in prompt


def test_acp_prompt_display_copy_else_branch() -> None:
    prompt = build_acp_author_system_prompt(template_mode="composition")
    assert "displayCopy ELIF displayCopyMode=text_free" in prompt
