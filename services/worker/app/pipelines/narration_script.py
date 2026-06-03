from __future__ import annotations

from typing import Any


def _normalize_text(value: str) -> str:
    return " ".join(str(value).strip().lower().split())


def is_creative_direction_text(
    script: str,
    *,
    slot: dict[str, Any] | None,
    visual: str = "",
) -> bool:
    """True when script is slot direction metadata, not spoken narration."""
    script_norm = _normalize_text(script)
    if not script_norm:
        return False
    candidates = [visual]
    if slot is not None:
        candidates.extend(
            [
                str(slot.get("scriptIntent", "")),
                str(slot.get("visualIntent", "")),
            ]
        )
    for candidate in candidates:
        if candidate and script_norm == _normalize_text(candidate):
            return True
    direction_prefixes = (
        "present ",
        "display ",
        "prompt ",
        "capture ",
        "highlight ",
        "encourage ",
        "show ",
    )
    if any(script_norm.startswith(prefix) for prefix in direction_prefixes):
        return True
    return False


def sanitize_storyboard_narration(
    storyboard: list[dict[str, Any]],
    *,
    structure: dict[str, Any],
) -> list[dict[str, Any]]:
    """Drop invalid narration scripts; never backfill from sample ASR transcript."""
    slots_by_id = {
        str(slot["id"]): slot
        for slot in structure.get("slots", [])
        if isinstance(slot, dict) and slot.get("id")
    }

    sanitized: list[dict[str, Any]] = []
    for scene in storyboard:
        if not isinstance(scene, dict):
            continue
        item = dict(scene)
        slot = slots_by_id.get(str(item.get("slotId", "")))
        script = str(item.get("script", "")).strip()
        visual = str(item.get("visual", "")).strip()

        if script and is_creative_direction_text(script, slot=slot, visual=visual):
            item["script"] = ""
        else:
            item["script"] = script
        sanitized.append(item)
    return sanitized
