from __future__ import annotations

from typing import Any


def _scene_for_slot(slot_id: str, storyboard: list[dict[str, Any]]) -> dict[str, Any] | None:
    for scene in storyboard:
        if isinstance(scene, dict) and scene.get("slotId") == slot_id:
            return scene
    return None


def _packaging_overlay_for_slot(
    slot_id: str,
    packaging_plan: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not isinstance(packaging_plan, dict):
        return None
    overlays = packaging_plan.get("slotOverlays") or packaging_plan.get("overlays")
    if not isinstance(overlays, list):
        return None
    for item in overlays:
        if isinstance(item, dict) and item.get("slotId") == slot_id:
            return dict(item)
    return None


def build_finish_brief(
    *,
    gap_item: dict[str, Any],
    slot: dict[str, Any],
    storyboard_scene: dict[str, Any] | None,
    base_media: dict[str, Any] | None,
    packaging_plan: dict[str, Any] | None = None,
    source_provider: str | None = None,
    duration_sec: float | None = None,
) -> dict[str, Any]:
    completion_mode = str(gap_item.get("completionMode") or "source_only")
    finish_intent = str(gap_item.get("finishIntent") or "").strip()
    packaging_requirements = list(slot.get("packagingRequirements") or [])
    packaging_hint = str(slot.get("packagingHint") or "").strip()

    brief: dict[str, Any] = {
        "completionMode": completion_mode,
        "constraints": ["do_not_replace_base_media", "keep_base_video_visible"],
    }
    if finish_intent:
        brief["finishIntent"] = finish_intent
    if packaging_requirements:
        brief["packagingRequirements"] = packaging_requirements
    if packaging_hint:
        brief["packagingHint"] = packaging_hint
    if storyboard_scene:
        brief["storyboardScene"] = {
            "script": str(storyboard_scene.get("script") or ""),
            "visual": str(storyboard_scene.get("visual") or ""),
        }
    if base_media:
        brief["baseMedia"] = dict(base_media)
    if source_provider:
        brief["sourceProvider"] = source_provider
    if duration_sec is not None and duration_sec > 0:
        brief["durationSec"] = round(float(duration_sec), 2)

    overlay = _packaging_overlay_for_slot(str(slot.get("id", "")), packaging_plan)
    if overlay:
        brief["packagingOverlay"] = overlay
    return brief


def build_finish_brief_for_action(
    *,
    action: dict[str, Any],
    slot: dict[str, Any],
    storyboard: list[dict[str, Any]],
    gap_item: dict[str, Any] | None,
    base_media: dict[str, Any] | None,
    packaging_plan: dict[str, Any] | None,
    source_provider: str | None,
    duration_sec: float | None,
) -> dict[str, Any]:
    gap = gap_item or {}
    if isinstance(action.get("finishBrief"), dict):
        brief = dict(action["finishBrief"])
    else:
        scene = _scene_for_slot(str(action.get("slotId", "")), storyboard)
        brief = build_finish_brief(
            gap_item=gap,
            slot=slot,
            storyboard_scene=scene,
            base_media=base_media,
            packaging_plan=packaging_plan,
            source_provider=source_provider,
            duration_sec=duration_sec,
        )
    if base_media and "baseMedia" not in brief:
        brief["baseMedia"] = dict(base_media)
    if source_provider:
        brief["sourceProvider"] = source_provider
    return brief
