from __future__ import annotations

from pathlib import Path

from composition.skills.catalog import SkillCatalog, SkillEntry

_L0_STOP_RULES = """\
# L0 STOP RULES (read first)
- Use ONLY videomaker-composition MCP tools in scratch; never Read/Grep/Shell repo .py source.
- Never set VM_ACP_FIXTURE_LINT; production lint must pass copy guard and HyperFrames lint.
- Read brief via read_author_brief MCP (or scratch/AUTHOR_BRIEF.md); never Read task.json from repo paths.
- displayCopy IF allowedDisplayCopy non-empty → only those strings may appear on screen.
- displayCopy ELIF displayCopyMode=text_free → no readable Chinese/VO copy on screen.
- Flow: skill_view → read_author_brief → composition_validate_draft → write scratch/draft.json → composition_lint_scratch_file (max 2) → write_material_spec → STOP.
- Do NOT call composition_lint_draft repeatedly with the same inline JSON; after validate, persist draft to scratch/draft.json and lint via composition_lint_scratch_file.
- Gate revise with mustChangeSpec: specHash MUST differ from existingSpecHash.
- Lint large drafts: write draft.json in scratch → composition_lint_scratch_file(relative_path)."""

_L1_DECISION = """\
# L1 decision tree
1. skill_view required private/public skills from available_skills (names only; use skill_view not Read).
2. read_author_brief → authorContract + renderPolicy + editInstruction (sole brief).
3. Draft MaterialSpec; composition_validate_draft (schema); write scratch/draft.json; composition_lint_scratch_file at most twice; then write_material_spec once.
4. write_material_spec once to scratch material-spec.json; do not use filesystem writes or helper scripts."""


def build_acp_author_system_prompt(
    repo_root: Path | None = None,
    *,
    template_mode: str = "composition",
    pattern_l0: list[dict] | None = None,
) -> str:
    catalog = SkillCatalog(repo_root=repo_root)
    extra: list[SkillEntry] = []
    for item in pattern_l0 or []:
        location = str(item.get("location", "")).strip()
        if not location:
            continue
        extra.append(
            SkillEntry(
                name=str(item.get("id", "pattern")),
                description=str(item.get("summary", "composition pattern")),
                location=location,
            )
        )
    template_note = (
        "template=composition with composition.bodyHtml/styles/timelineScript (shell tl)."
        if template_mode == "composition"
        else "template=benefit-card; empty title/bullets when allowedDisplayCopy empty."
    )
    parts = [
        _L0_STOP_RULES,
        "",
        _L1_DECISION,
        "",
        catalog.render_available_skills_xml(extra=extra or None),
        "",
        catalog.skill_usage_rule_xml(acp_author=True),
        "",
        "# Output",
        template_note,
        "Submit via write_material_spec only.",
    ]
    return "\n".join(parts)
