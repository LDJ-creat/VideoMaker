from __future__ import annotations

from pathlib import Path

from composition.skills.catalog import SkillCatalog, SkillEntry


def build_bootstrap_system_prompt(
    *,
    repo_root: Path | None = None,
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
    parts = [
        "# Role",
        "Author MaterialSpec JSON for VideoMaker slot-level HyperFrames clips.",
        "",
        catalog.render_available_skills_xml(extra=extra or None),
        "",
        catalog.skill_usage_rule_xml(),
        "",
        "# Output",
        "Use submit_material_spec with JSON matching material-spec schema.",
        "Prefer template=composition with composition.bodyHtml for rich motion graphics.",
    ]
    return "\n".join(parts)
