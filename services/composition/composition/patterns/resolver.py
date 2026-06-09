from __future__ import annotations

import json
from typing import Any

from composition.patterns.deposit import composition_draft_dir


def _role_matches(slot_role: str, roles: list[Any]) -> bool:
    if not slot_role:
        return True
    normalized = slot_role.strip().lower()
    for item in roles:
        if str(item).strip().lower() == normalized:
            return True
    return False


def _published_pattern_cards(
    storage_root,
    *,
    slot_role: str,
    limit: int,
) -> list[dict[str, Any]]:
    knowledge_root = storage_root / "knowledge"
    if not knowledge_root.is_dir():
        return []
    cards: list[dict[str, Any]] = []
    for category_dir in sorted(knowledge_root.iterdir(), reverse=True):
        if not category_dir.is_dir():
            continue
        for entry_dir in sorted(category_dir.iterdir(), reverse=True):
            if not entry_dir.is_dir():
                continue
            skill = entry_dir / "composition-skill.md"
            meta_path = entry_dir / "entry-meta.json"
            if not skill.is_file():
                continue
            meta: dict[str, Any] = {}
            if meta_path.is_file():
                try:
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    meta = {}
            if meta.get("entryKind") == "structure":
                continue
            if meta.get("entryKind") != "composition_pattern" and not (entry_dir / "spec.template.json").is_file():
                continue
            roles = meta.get("slotRoles") or []
            if isinstance(roles, str):
                roles = [roles]
            if not _role_matches(slot_role, roles if isinstance(roles, list) else []):
                continue
            rel = skill.relative_to(storage_root).as_posix()
            cards.append(
                {
                    "id": entry_dir.name,
                    "summary": str(meta.get("title") or f"published pattern {entry_dir.name}"),
                    "location": rel,
                    "slotRole": roles[0] if roles else slot_role,
                    "source": "published",
                }
            )
            if len(cards) >= limit:
                return cards
    return cards


def _draft_pattern_cards(
    storage_root,
    *,
    project_id: str,
    slot_role: str,
    limit: int,
) -> list[dict[str, Any]]:
    drafts_root = storage_root / "projects" / project_id / "knowledge" / "drafts" / "composition"
    if not drafts_root.is_dir():
        return []
    cards: list[dict[str, Any]] = []
    for generation_dir in sorted(drafts_root.iterdir(), reverse=True):
        if not generation_dir.is_dir():
            continue
        for slot_dir in generation_dir.iterdir():
            if not slot_dir.is_dir():
                continue
            skill = slot_dir / "composition-skill.md"
            if not skill.is_file():
                continue
            meta_path = slot_dir / "entry-meta.json"
            roles: list[Any] = []
            title = f"composition pattern for {slot_dir.name}"
            if meta_path.is_file():
                try:
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                    roles = meta.get("slotRoles") or []
                    title = str(meta.get("title") or title)
                except json.JSONDecodeError:
                    pass
            if isinstance(roles, str):
                roles = [roles]
            if not _role_matches(slot_role, roles):
                continue
            rel = skill.relative_to(storage_root).as_posix()
            cards.append(
                {
                    "id": f"{generation_dir.name}-{slot_dir.name}",
                    "summary": title,
                    "location": rel,
                    "slotRole": roles[0] if roles else slot_dir.name,
                    "source": "draft",
                }
            )
            if len(cards) >= limit:
                return cards
    return cards


def pattern_l0_cards(
    storage_root,
    *,
    project_id: str,
    slot_role: str,
    limit: int = 3,
) -> list[dict[str, Any]]:
    """Return lightweight pattern index cards for bootstrap available_skills."""
    published = _published_pattern_cards(storage_root, slot_role=slot_role, limit=limit)
    remaining = max(0, limit - len(published))
    drafts = _draft_pattern_cards(
        storage_root,
        project_id=project_id,
        slot_role=slot_role,
        limit=remaining,
    ) if remaining else []
    seen_locations = {item["location"] for item in published}
    merged = list(published)
    for item in drafts:
        if item["location"] in seen_locations:
            continue
        merged.append(item)
        if len(merged) >= limit:
            break
    return merged
