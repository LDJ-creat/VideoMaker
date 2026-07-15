from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_AUTHOR_BRIEF_KEYS = (
    "slot",
    "slotId",
    "slotTiming",
    "authorContract",
    "renderPolicy",
    "editInstruction",
    "finishBrief",
    "compositionAuthorBrief",
    "visualStyleBible",
    "materialGateRevise",
    "existingSpecHash",
)

_REQUIRED_SKILL_NAMES = (
    "videomaker-composition",
    "videomaker-visual-craft",
)

_SKILL_SUMMARY_MAX_CHARS = 6000
_GATE_REVISE_SKILL_SUMMARY_MAX_CHARS = 3000


def _brief_subset(author_payload: dict[str, Any]) -> dict[str, Any]:
    brief: dict[str, Any] = {}
    for key in _AUTHOR_BRIEF_KEYS:
        if key in author_payload:
            brief[key] = author_payload[key]
    contract = author_payload.get("authorContract")
    if isinstance(contract, dict):
        brief["authorContract"] = contract
    return brief


def _render_author_brief_md(author_payload: dict[str, Any]) -> str:
    brief = _brief_subset(author_payload)
    lines = [
        "# Author Brief (scratch)",
        "",
        "Use MCP `read_author_brief` for the same JSON. Do not Read task.json from disk.",
        "",
        "## JSON",
        "",
        "```json",
        json.dumps(brief, ensure_ascii=False, indent=2),
        "```",
    ]
    edit = str(author_payload.get("editInstruction") or "").strip()
    if edit:
        lines.extend(["", "## Edit instruction", "", edit])
    contract = author_payload.get("authorContract")
    if isinstance(contract, dict):
        allowed = contract.get("allowedDisplayCopy")
        if isinstance(allowed, list) and allowed:
            lines.extend(["", "## Allowed on-screen copy", ""])
            for item in allowed:
                lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def _load_skill_summary(repo_root: Path, skill_name: str) -> str:
    for prefix in ("skills/private", "skills/public"):
        skill_md = repo_root / prefix / skill_name / "SKILL.md"
        if skill_md.is_file():
            text = skill_md.read_text(encoding="utf-8")
            if len(text) > 2000:
                return text[:2000] + "\n\n...(truncated; use skill_view for full content)...\n"
            return text
    return f"(skill {skill_name} not found)\n"


def _render_skills_summary_md(repo_root: Path, *, max_chars: int = _SKILL_SUMMARY_MAX_CHARS) -> str:
    parts = [
        "# Skills Summary (scratch bootstrap)",
        "",
        "Prefer `skill_view` by skill name from available_skills. Do not Read repo SKILL.md files.",
        "",
    ]
    total = 0
    for name in _REQUIRED_SKILL_NAMES:
        chunk = _load_skill_summary(repo_root, name)
        section = f"## {name}\n\n{chunk}\n"
        if total + len(section) > max_chars:
            parts.append(f"## {name}\n\n(truncated — call skill_view)\n")
            break
        parts.append(section)
        total += len(section)
    return "\n".join(parts)


def bootstrap_acp_scratch(
    *,
    scratch_dir: Path,
    author_payload: dict[str, Any],
    repo_root: Path,
) -> None:
    scratch_dir.mkdir(parents=True, exist_ok=True)
    (scratch_dir / "AUTHOR_BRIEF.md").write_text(
        _render_author_brief_md(author_payload),
        encoding="utf-8",
    )
    from app.pipelines.material_slot_revise import MATERIAL_GATE_REVISE_SOURCE

    max_chars = _SKILL_SUMMARY_MAX_CHARS
    gate = author_payload.get("materialGateRevise")
    if isinstance(gate, dict) and gate.get("source") == MATERIAL_GATE_REVISE_SOURCE:
        max_chars = _GATE_REVISE_SKILL_SUMMARY_MAX_CHARS
    (scratch_dir / "SKILLS_SUMMARY.md").write_text(
        _render_skills_summary_md(repo_root.resolve(), max_chars=max_chars),
        encoding="utf-8",
    )
