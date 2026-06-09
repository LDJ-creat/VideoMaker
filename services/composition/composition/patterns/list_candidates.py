from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from composition.patterns.deposit import (
    composition_drafts_generation_dir,
    composition_pattern_entry_id,
)
from composition.patterns.lint_verify import lint_log_confirms_pass
from composition.patterns.sanitize import load_generation_plan_context, storyboard_summary_for_slot


def list_composition_pattern_candidates(
    storage_root: Path,
    *,
    project_id: str,
    generation_id: str,
    get_published_entry: Any | None = None,
) -> list[dict[str, Any]]:
    drafts_root = composition_drafts_generation_dir(
        storage_root,
        project_id=project_id,
        generation_id=generation_id,
    )
    if not drafts_root.is_dir():
        return []

    try:
        plan_context = load_generation_plan_context(
            storage_root,
            project_id=project_id,
            generation_id=generation_id,
            slot_id="",
        )
    except FileNotFoundError:
        return []

    plan = plan_context.get("plan") if isinstance(plan_context.get("plan"), dict) else {}
    storyboard = plan.get("storyboard") if isinstance(plan.get("storyboard"), list) else []
    hf_slot_ids: set[str] = set()
    action_by_slot: dict[str, str] = {}
    for action in plan.get("completionActions") or []:
        if not isinstance(action, dict):
            continue
        provider = str(action.get("provider") or action.get("strategy") or "")
        if provider != "hyperframes_material":
            continue
        slot_id = str(action.get("slotId") or "").strip()
        if slot_id:
            hf_slot_ids.add(slot_id)
            action_by_slot[slot_id] = str(action.get("id") or "")

    if not hf_slot_ids:
        return []

    candidates: list[dict[str, Any]] = []
    for slot_dir in sorted(drafts_root.iterdir()):
        if not slot_dir.is_dir():
            continue
        slot_id = slot_dir.name
        if slot_id not in hf_slot_ids:
            continue
        lint_log = slot_dir / "lint-log.json"
        meta_path = slot_dir / "entry-meta.json"
        if not lint_log_confirms_pass(lint_log):
            continue
        meta: dict[str, Any] = {}
        if meta_path.is_file():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                meta = {}
        if meta.get("lintPassed") is False:
            continue
        roles = meta.get("slotRoles") or []
        if isinstance(roles, str):
            roles = [roles]
        slot_role = str(roles[0] if roles else slot_id)
        entry_id = composition_pattern_entry_id(generation_id, slot_id)
        published_entry = None
        if get_published_entry is not None:
            published = get_published_entry(entry_id)
            if published is not None:
                published_entry = {
                    "id": published.get("id"),
                    "title": published.get("title"),
                    "updatedAt": published.get("updatedAt"),
                }
        candidates.append(
            {
                "slotId": slot_id,
                "slotRole": slot_role,
                "storyboardSummary": storyboard_summary_for_slot(storyboard, slot_id),
                "actionId": action_by_slot.get(slot_id),
                "draftReady": True,
                "publishedEntry": published_entry,
            }
        )
    return candidates
