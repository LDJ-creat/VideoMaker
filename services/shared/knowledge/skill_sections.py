from __future__ import annotations

import re
from typing import Any


_SECTION_ALIASES = {
    "适用场景": "scenarios",
    "结构要点": "structure_points",
    "槽位模板": "slot_template",
    "迁移注意": "migration_notes",
}


def extract_skill_sections(markdown: str) -> dict[str, str]:
    """Parse markdown H2 sections for progressive disclosure (L1)."""
    sections: dict[str, str] = {}
    current_key = "_preamble"
    current_lines: list[str] = []

    for line in markdown.splitlines():
        heading = re.match(r"^##\s+(.+?)\s*$", line.strip())
        if heading:
            sections[current_key] = "\n".join(current_lines).strip()
            title = heading.group(1).strip()
            current_key = _SECTION_ALIASES.get(title, title)
            current_lines = []
        else:
            current_lines.append(line)

    sections[current_key] = "\n".join(current_lines).strip()
    return {key: value for key, value in sections.items() if value}


def build_l1_summary(markdown: str, *, max_chars: int = 4000) -> str:
    sections = extract_skill_sections(markdown)
    parts: list[str] = []
    for key in ("_preamble", "scenarios", "structure_points", "slot_template", "migration_notes"):
        text = sections.get(key, "")
        if text:
            parts.append(text)
    combined = "\n\n".join(parts).strip()
    if len(combined) <= max_chars:
        return combined
    return combined[: max_chars - 3] + "..."


def build_knowledge_context_payload(
    *,
    primary_entry: dict[str, Any] | None,
    primary_skill_md: str | None,
    reference_entries: list[dict[str, Any]],
    reference_skill_mds: list[str],
    level: int = 1,
) -> dict[str, Any]:
    """Build agent-facing knowledge context at disclosure level 1 or 2."""
    payload: dict[str, Any] = {
        "level": level,
        "primary": None,
        "references": [],
    }
    if primary_entry is None:
        return payload

    if level >= 2 and primary_skill_md:
        primary_content = primary_skill_md
    elif primary_skill_md:
        primary_content = build_l1_summary(primary_skill_md)
    else:
        primary_content = str(primary_entry.get("summary", ""))

    payload["primary"] = {
        "entryId": primary_entry.get("id"),
        "title": primary_entry.get("title"),
        "summary": primary_entry.get("summary"),
        "slotPattern": primary_entry.get("slotPattern"),
        "hookType": primary_entry.get("hookType"),
        "content": primary_content,
    }

    for entry, skill_md in zip(reference_entries, reference_skill_mds, strict=False):
        ref_content = build_l1_summary(skill_md) if skill_md else str(entry.get("summary", ""))
        payload["references"].append(
            {
                "entryId": entry.get("id"),
                "title": entry.get("title"),
                "summary": entry.get("summary"),
                "content": ref_content,
            }
        )
    return payload
