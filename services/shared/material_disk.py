from __future__ import annotations

from pathlib import Path
from typing import Any

MATERIAL_PROVIDERS = frozenset(
    {
        "asset_reuse",
        "stock_media_search",
        "image_generation",
        "video_generation",
        "tts",
        "hyperframes_material",
    }
)

MASTER_TTS_SLOT_ID = "__master__"
MIN_STOCK_VIDEO_BYTES = 100_000
MIN_HYPERFRAMES_VIDEO_BYTES = 15_000

MATERIAL_REVIEW_APPROVABLE_SLOT_STATUSES = frozenset(
    {"agent_passed", "agent_failed", "skipped", "review_unavailable"}
)


def _min_video_bytes_for_path(path: Path) -> int:
    name = path.name.lower()
    if name.startswith("action-slot-"):
        return MIN_HYPERFRAMES_VIDEO_BYTES
    if "-stock" in name or name.endswith("-reuse.mp4"):
        return MIN_STOCK_VIDEO_BYTES
    return MIN_STOCK_VIDEO_BYTES


def is_valid_visual_artifact(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size <= 0:
        return False
    if path.suffix.lower() in {".mp4", ".webm", ".mov", ".mkv"}:
        return path.stat().st_size >= _min_video_bytes_for_path(path)
    return True


def expected_output_path(action: dict[str, Any], generated_root: Path) -> Path:
    slot_id = str(action["slotId"])
    provider = str(action.get("provider") or action.get("strategy", ""))
    if provider == "image_generation":
        return generated_root / f"{slot_id}.png"
    if provider == "video_generation":
        return generated_root / f"{slot_id}.mp4"
    if provider == "tts":
        if slot_id == MASTER_TTS_SLOT_ID:
            return generated_root / "master.wav"
        return generated_root / f"{slot_id}.wav"
    if provider == "asset_reuse":
        return generated_root / f"{slot_id}-reuse.mp4"
    if provider == "stock_media_search":
        for suffix in (".mp4", ".jpg", ".png"):
            candidate = generated_root / f"{slot_id}-stock{suffix}"
            if candidate.is_file():
                return candidate
        return generated_root / f"{slot_id}-stock.mp4"
    if provider == "hyperframes_material":
        action_id = str(action.get("id") or f"action-{slot_id}")
        return generated_root / f"{action_id}.mp4"
    return generated_root / f"{slot_id}.bin"


def action_artifact_satisfied(action: dict[str, Any], generated_root: Path) -> bool:
    artifact_ref = action.get("artifactRef")
    if isinstance(artifact_ref, dict):
        uri = str(artifact_ref.get("uri", "")).strip()
        if uri:
            path = Path(uri)
            if is_valid_visual_artifact(path):
                return True
    output = expected_output_path(action, generated_root)
    return is_valid_visual_artifact(output)


def material_review_slot_artifact_satisfied(
    *,
    action: dict[str, Any] | None,
    generated_root: Path,
    slot_status: str,
) -> bool:
    """Gate approve artifact check; agent_failed allows any non-empty on-disk preview."""
    if action is None:
        return False
    output = expected_output_path(action, generated_root)
    if slot_status in {"agent_failed", "review_unavailable"}:
        return output.is_file() and output.stat().st_size > 0
    return action_artifact_satisfied(action, generated_root)


def infer_completed_slot_ids(
    completion_actions: list[dict[str, Any]],
    generated_root: Path,
) -> list[str]:
    """Infer structure slot ids with usable visual outputs on disk."""
    if not generated_root.is_dir():
        return []

    by_slot: dict[str, list[dict[str, Any]]] = {}
    for action in completion_actions:
        provider = str(action.get("provider") or action.get("strategy", ""))
        if provider not in MATERIAL_PROVIDERS or provider == "tts":
            continue
        slot_id = str(action.get("slotId") or "").strip()
        if not slot_id or slot_id == MASTER_TTS_SLOT_ID:
            continue
        by_slot.setdefault(slot_id, []).append(action)

    completed: list[str] = []
    for slot_id, actions in by_slot.items():
        if _slot_visual_complete(actions, generated_root):
            completed.append(slot_id)
    return sorted(completed)


def collect_visual_slot_ids(completion_actions: list[dict[str, Any]]) -> set[str]:
    visual_slot_ids: set[str] = set()
    for action in completion_actions:
        if not isinstance(action, dict):
            continue
        slot_id = str(action.get("slotId") or "").strip()
        provider = str(action.get("provider") or action.get("strategy") or "")
        if not slot_id or slot_id == MASTER_TTS_SLOT_ID or provider == "tts":
            continue
        if provider in MATERIAL_PROVIDERS or provider:
            visual_slot_ids.add(slot_id)
    return visual_slot_ids


def terminal_visual_action_by_slot(
    completion_actions: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    terminal: dict[str, dict[str, Any]] = {}
    for action in completion_actions:
        if not isinstance(action, dict):
            continue
        slot_id = str(action.get("slotId") or "").strip()
        if slot_id and slot_id != MASTER_TTS_SLOT_ID:
            terminal[slot_id] = action
    return terminal


def material_review_approvable(
    *,
    state: dict[str, Any],
    completion_actions: list[dict[str, Any]],
    generated_root: Path | None = None,
) -> tuple[bool, str]:
    slots_state = state.get("slots")
    if not isinstance(slots_state, dict):
        return False, "Material review slot state missing"

    visual_slot_ids = collect_visual_slot_ids(completion_actions)
    if not visual_slot_ids:
        return True, ""

    terminal_by_slot = terminal_visual_action_by_slot(completion_actions)
    for slot_id in sorted(visual_slot_ids):
        entry = slots_state.get(slot_id)
        if not isinstance(entry, dict):
            return False, f"Slot {slot_id} has no review state"
        status = str(entry.get("status") or "")
        if status not in MATERIAL_REVIEW_APPROVABLE_SLOT_STATUSES:
            return False, f"Slot {slot_id} is not ready for approval (status={status or 'unknown'})"
        if generated_root is not None:
            action = terminal_by_slot.get(slot_id)
            if not isinstance(action, dict):
                return False, f"Slot {slot_id} has no terminal completion action"
            if not material_review_slot_artifact_satisfied(
                action=action,
                generated_root=generated_root,
                slot_status=status,
            ):
                return False, f"Slot {slot_id} is missing a usable preview artifact"
    return True, ""


def _slot_visual_complete(actions: list[dict[str, Any]], generated_root: Path) -> bool:
    finish_actions = [
        action
        for action in actions
        if str(action.get("id") or "").endswith("-finish")
    ]
    if finish_actions:
        return any(action_artifact_satisfied(action, generated_root) for action in finish_actions)

    hyperframes_actions = [
        action
        for action in actions
        if str(action.get("provider") or action.get("strategy", "")) == "hyperframes_material"
    ]
    if hyperframes_actions:
        return any(action_artifact_satisfied(action, generated_root) for action in hyperframes_actions)

    return any(action_artifact_satisfied(action, generated_root) for action in actions)
