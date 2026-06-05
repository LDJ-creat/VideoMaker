from __future__ import annotations

import re
from typing import Any


_SECTION_ALIASES = {
    "适用场景": "scenarios",
    "结构要点": "structure_points",
    "口播手法": "vo_techniques",
    "画面语言": "visual_language",
    "包装清单": "packaging_checklist",
    "节奏与音频设计": "rhythm_audio",
    "槽位模板": "slot_template",
    "迁移示例": "migration_examples",
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
    for key in (
        "_preamble",
        "scenarios",
        "structure_points",
        "vo_techniques",
        "visual_language",
        "packaging_checklist",
        "rhythm_audio",
        "slot_template",
        "migration_examples",
        "migration_notes",
    ):
        text = sections.get(key, "")
        if text:
            parts.append(text)
    combined = "\n\n".join(parts).strip()
    if len(combined) <= max_chars:
        return combined
    return combined[: max_chars - 3] + "..."


def _build_structure_hints(
    *,
    video_structure: dict[str, Any] | None,
    sample_analysis: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if video_structure is None and sample_analysis is None:
        return None
    hints: dict[str, Any] = {}
    if isinstance(video_structure, dict):
        slots = video_structure.get("slots") if isinstance(video_structure.get("slots"), list) else []
        templates = [
            str(slot.get("migrationTemplate"))
            for slot in slots
            if isinstance(slot, dict) and slot.get("migrationTemplate")
        ]
        if templates:
            hints["migrationTemplates"] = templates[:8]
        segments = (
            video_structure.get("narrative", {}).get("segments")
            if isinstance(video_structure.get("narrative"), dict)
            else []
        )
        vo_styles = [
            segment.get("voStyle")
            for segment in segments or []
            if isinstance(segment, dict) and segment.get("voStyle")
        ]
        if vo_styles:
            hints["voStyles"] = vo_styles[:4]
    if isinstance(sample_analysis, dict):
        audio_profile = sample_analysis.get("audioProfile")
        if isinstance(audio_profile, dict):
            hints["audioProfileSummary"] = {
                "hasVoiceover": audio_profile.get("hasVoiceover"),
                "hasBgm": audio_profile.get("hasBgm"),
                "tempoBpm": audio_profile.get("tempoBpm"),
                "voiceoverCoveragePct": (audio_profile.get("metrics") or {}).get(
                    "voiceoverCoveragePct"
                ),
            }
    return hints or None


def build_knowledge_context_payload(
    *,
    primary_entry: dict[str, Any] | None,
    primary_skill_md: str | None,
    reference_entries: list[dict[str, Any]],
    reference_skill_mds: list[str],
    level: int = 1,
    video_structure: dict[str, Any] | None = None,
    sample_analysis: dict[str, Any] | None = None,
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

    hints = _build_structure_hints(
        video_structure=video_structure,
        sample_analysis=sample_analysis,
    )
    if hints and level >= 2:
        payload["structureHints"] = hints
    return payload
