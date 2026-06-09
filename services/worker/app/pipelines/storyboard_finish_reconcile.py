"""Reconcile gap finish intent after storyboard approval."""

from __future__ import annotations

from typing import Any

PACKAGING_KEYWORDS = (
    "字幕",
    "角标",
    "lower third",
    "lower_third",
    "花字",
    "卡片",
    "caption",
    "overlay",
    "包装",
    "标题条",
)


def _needs_polish_from_scene(scene: dict[str, Any] | None) -> bool:
    if not isinstance(scene, dict):
        return False
    text = f"{scene.get('visual', '')} {scene.get('script', '')}".lower()
    return any(keyword in text for keyword in PACKAGING_KEYWORDS)


def reconcile_gap_finish_from_storyboard(
    gap_report: dict[str, Any],
    *,
    storyboard: list[dict[str, Any]],
    structure: dict[str, Any],
) -> dict[str, Any]:
    slots_by_id = {
        slot["id"]: slot
        for slot in structure.get("slots", [])
        if isinstance(slot, dict) and slot.get("id")
    }
    scenes_by_slot = {
        str(scene.get("slotId")): scene
        for scene in storyboard
        if isinstance(scene, dict) and scene.get("slotId")
    }

    for bucket in ("missingSlots", "weakSlots"):
        updated: list[dict[str, Any]] = []
        for item in gap_report.get(bucket, []):
            if not isinstance(item, dict):
                continue
            slot_id = str(item.get("slotId", ""))
            slot = slots_by_id.get(slot_id, {})
            scene = scenes_by_slot.get(slot_id)
            merged = dict(item)
            packaging_reqs = list(slot.get("packagingRequirements") or [])
            mode = str(merged.get("completionMode") or "source_only")
            fixes = list(merged.get("suggestedFixes") or [])

            if packaging_reqs:
                if fixes == ["hyperframes_material"]:
                    merged["completionMode"] = "hf_native"
                elif mode == "source_only":
                    merged["completionMode"] = "source_then_polish"
                    if "hyperframes_material" not in fixes:
                        fixes.append("hyperframes_material")
                        merged["suggestedFixes"] = fixes
            elif _needs_polish_from_scene(scene) and mode == "source_only":
                merged["completionMode"] = "source_then_polish"
                if fixes and fixes[-1] != "hyperframes_material":
                    fixes.append("hyperframes_material")
                    merged["suggestedFixes"] = fixes
                intent = str(merged.get("finishIntent") or "").strip()
                visual = str((scene or {}).get("visual") or "").strip()
                if visual and visual not in intent:
                    merged["finishIntent"] = f"{intent}；分镜视觉：{visual}".strip("；")
            updated.append(merged)
        gap_report[bucket] = updated
    return gap_report
