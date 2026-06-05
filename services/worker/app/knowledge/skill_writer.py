from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from knowledge.index_builder import build_entry_meta
from knowledge.paths import draft_dir, rel_uri


def compose_skill_markdown(frontmatter: dict[str, Any], body: str) -> str:
    lines = ["---"]
    for key, value in frontmatter.items():
        if value is None:
            continue
        if isinstance(value, str) and "\n" in value:
            lines.append(f"{key}: |")
            lines.extend(f"  {part}" for part in value.splitlines())
        else:
            lines.append(f"{key}: {value}")
    lines.append("---")
    lines.append("")
    lines.append(body.strip())
    return "\n".join(lines) + "\n"


def write_knowledge_draft(
    storage_root: Path,
    *,
    project_id: str,
    sample_id: str,
    structure: dict[str, Any],
    skill_output: dict[str, Any],
    sample_analysis: dict[str, Any] | None = None,
) -> dict[str, str]:
    target = draft_dir(storage_root, project_id, sample_id)
    target.mkdir(parents=True, exist_ok=True)

    frontmatter = dict(skill_output.get("frontmatter") or {})
    meta = build_entry_meta(
        structure,
        title=str(frontmatter.get("title") or "结构经验"),
        category=str(frontmatter.get("category") or "通用短视频"),
        style=str(frontmatter.get("style") or "标准结构"),
        summary=str(frontmatter.get("summary") or ""),
        hook_type=frontmatter.get("hookType"),
        sample_analysis=sample_analysis,
    )
    frontmatter = {**meta, **frontmatter}

    skill_md = compose_skill_markdown(frontmatter, str(skill_output.get("markdown", "")))
    skill_path = target / "structure-skill.md"
    structure_path = target / "video-structure.json"
    meta_path = target / "entry-meta.json"

    skill_path.write_text(skill_md, encoding="utf-8")
    structure_path.write_text(json.dumps(structure, indent=2, ensure_ascii=False), encoding="utf-8")
    meta_path.write_text(json.dumps(frontmatter, indent=2, ensure_ascii=False), encoding="utf-8")

    return {
        "skillMdUri": rel_uri(storage_root, skill_path),
        "structureJsonUri": rel_uri(storage_root, structure_path),
        "entryMetaUri": rel_uri(storage_root, meta_path),
    }
