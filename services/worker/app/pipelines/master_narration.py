from __future__ import annotations

import re
from typing import Any

from app.pipelines.narration_script import is_creative_direction_text

_CLAUSE_SPLIT = re.compile(r"(?<=[。！？!?；;])\s*")


def _normalize_compare(text: str) -> str:
    return re.sub(r"\s+", "", text.strip())


def split_master_into_clauses(master: str) -> list[str]:
    text = str(master).strip()
    if not text:
        return []
    parts = [part.strip() for part in _CLAUSE_SPLIT.split(text) if part.strip()]
    return parts if parts else [text]


def _scene_durations(scenes: list[dict[str, Any]]) -> list[float]:
    durations: list[float] = []
    for scene in scenes:
        start = float(scene.get("startSec", 0.0))
        end = float(scene.get("endSec", start))
        durations.append(max(0.0, end - start))
    return durations


def split_master_narration_by_duration(
    master: str,
    scenes: list[dict[str, Any]],
) -> list[str]:
    """Split full narration into per-scene chunks weighted by slot duration."""
    clauses = split_master_into_clauses(master)
    if not scenes:
        return []
    if not clauses:
        return [""] * len(scenes)

    indexed = sorted(
        enumerate(scenes),
        key=lambda item: float(item[1].get("startSec", 0.0)),
    )
    durations = [max(0.0, _scene_durations([scene])[0]) for _, scene in indexed]
    total_duration = sum(durations) or float(len(scenes))

    exact_shares = [len(clauses) * (duration / total_duration) for duration in durations]
    clause_counts = [int(share) for share in exact_shares]
    remainder = len(clauses) - sum(clause_counts)
    if remainder > 0:
        ranked = sorted(
            range(len(exact_shares)),
            key=lambda index: exact_shares[index] - clause_counts[index],
            reverse=True,
        )
        for index in ranked[:remainder]:
            clause_counts[index] += 1

    if len(clauses) >= len(clause_counts):
        while any(count == 0 for count in clause_counts):
            donor = max(range(len(clause_counts)), key=lambda index: clause_counts[index])
            if clause_counts[donor] <= 1:
                break
            recipient = next(index for index, count in enumerate(clause_counts) if count == 0)
            clause_counts[donor] -= 1
            clause_counts[recipient] += 1

    per_scene = [""] * len(scenes)
    cursor = 0
    for (scene_index, _), count in zip(indexed, clause_counts, strict=False):
        chunk = "".join(clauses[cursor : cursor + count]).strip()
        per_scene[scene_index] = chunk
        cursor += count
    return per_scene


def script_belongs_to_master(script: str, master: str) -> bool:
    script_norm = _normalize_compare(script)
    master_norm = _normalize_compare(master)
    if not script_norm or not master_norm:
        return False
    return script_norm in master_norm


def derive_master_from_storyboard(storyboard: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for scene in sorted(storyboard, key=lambda item: float(item.get("startSec", 0.0))):
        script = str(scene.get("script", "")).strip()
        if script:
            parts.append(script)
    return "".join(parts)


def apply_master_narration_to_storyboard(
    *,
    master_narration: str,
    storyboard: list[dict[str, Any]],
    structure: dict[str, Any],
) -> tuple[str, list[dict[str, Any]]]:
    """Align per-scene scripts to the full master narration layer."""
    master = str(master_narration).strip()
    if not master:
        master = derive_master_from_storyboard(storyboard)

    slots_by_id = {
        str(slot["id"]): slot
        for slot in structure.get("slots", [])
        if isinstance(slot, dict) and slot.get("id")
    }
    splits = split_master_narration_by_duration(master, storyboard) if master else [""] * len(storyboard)

    aligned: list[dict[str, Any]] = []
    for index, scene in enumerate(storyboard):
        if not isinstance(scene, dict):
            continue
        item = dict(scene)
        slot = slots_by_id.get(str(item.get("slotId", "")))
        script = str(item.get("script", "")).strip()
        visual = str(item.get("visual", "")).strip()
        split_script = splits[index] if index < len(splits) else ""

        if script and not is_creative_direction_text(script, slot=slot, visual=visual):
            if master and script_belongs_to_master(script, master):
                item["script"] = script
            elif split_script:
                item["script"] = split_script
            else:
                item["script"] = script
        elif split_script:
            item["script"] = split_script
        else:
            item["script"] = ""
        aligned.append(item)

    if master:
        return master, aligned
    return derive_master_from_storyboard(aligned), aligned
