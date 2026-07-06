from __future__ import annotations

from pathlib import Path

from composition.skills.catalog import SkillCatalog, SkillEntry

_L0_STOP_RULES = """\
# L0 STOP RULES (read first)
- Use ONLY videomaker-composition MCP tools in scratch; never Read/Grep/Shell repo .py source.
- Never set VM_ACP_FIXTURE_LINT; production lint must pass copy guard and HyperFrames lint.
- displayCopy IF allowedDisplayCopy non-empty → only those strings may appear on screen.
- displayCopy ELIF displayCopyMode=text_free → no readable Chinese/VO copy on screen.
- Flow: skill_view (listed skills) → read authorContract in user payload → composition_lint_draft → write_material_spec → STOP.
- Gate revise with mustChangeSpec: specHash MUST differ from existingSpecHash."""

_L1_DECISION = """\
# L1 decision tree
1. skill_view required private/public skills from available_skills.
2. Read authorContract + renderPolicy + editInstruction from user JSON (sole brief).
3. Draft MaterialSpec; lint loop via composition_lint_draft until ok.
4. write_material_spec once to scratch material-spec.json; do not use filesystem writes."""


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
