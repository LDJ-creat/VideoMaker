from __future__ import annotations

from pathlib import Path
from typing import Any

FINISH_ACTION_SUFFIXES = ("-finish", "-ken-burns")


def resolve_slot_base_media(slot_id: str, generated_root: Path) -> dict[str, Any] | None:
    """Resolve primary source artifact for a slot after source provider execution."""
    candidates: list[tuple[str, str]] = [
        (f"{slot_id}-reuse.mp4", "video"),
        (f"{slot_id}-stock.mp4", "video"),
        (f"{slot_id}.mp4", "video"),
        (f"{slot_id}-stock.jpg", "image"),
        (f"{slot_id}-stock.png", "image"),
        (f"{slot_id}-stock.webp", "image"),
        (f"{slot_id}.png", "image"),
    ]
    for filename, media_type in candidates:
        path = generated_root / filename
        if path.is_file() and path.stat().st_size > 0:
            return {
                "id": f"base-{slot_id}",
                "type": media_type,
                "uri": str(path.resolve()),
                "createdAt": "1970-01-01T00:00:00Z",
            }
    return None


def is_finish_action(action_id: str) -> bool:
    return any(str(action_id).endswith(suffix) for suffix in FINISH_ACTION_SUFFIXES)
