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
