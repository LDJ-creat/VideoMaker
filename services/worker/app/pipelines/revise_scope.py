from __future__ import annotations

from typing import Any, Literal

MaterialScope = Literal["none", "scoped", "all"]

_ALL_MATERIAL_TOOLS = frozenset({"storyboard_agent", "full_pipeline"})
_SCOPED_MATERIAL_TOOLS = frozenset({"material_regen"})


def _storyboard_from_plan(source_plan: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(source_plan, dict):
        return []
    storyboard = source_plan.get("storyboard")
    if not isinstance(storyboard, list):
        return []
    return [scene for scene in storyboard if isinstance(scene, dict)]


def _scene_ids_from_intent(intent: dict[str, Any]) -> list[str]:
    scene_ids: list[str] = []
    raw_scene_ids = intent.get("sceneIds")
    if isinstance(raw_scene_ids, list):
        scene_ids.extend(str(item) for item in raw_scene_ids if item)
    params = intent.get("params") if isinstance(intent.get("params"), dict) else {}
    scene_id = params.get("sceneId")
    if scene_id:
        scene_ids.append(str(scene_id))
    return list(dict.fromkeys(scene_ids))


def _slot_ids_from_intent(intent: dict[str, Any]) -> list[str]:
    slot_ids: list[str] = []
    raw_slot_ids = intent.get("slotIds")
    if isinstance(raw_slot_ids, list):
        slot_ids.extend(str(item) for item in raw_slot_ids if item)
    params = intent.get("params") if isinstance(intent.get("params"), dict) else {}
    slot_id = params.get("slotId")
    if slot_id:
        slot_ids.append(str(slot_id))
    return list(dict.fromkeys(slot_ids))


def resolve_slot_ids_from_intents(
    intents: list[dict[str, Any]],
    *,
    storyboard: list[dict[str, Any]] | None = None,
) -> list[str]:
    scenes = storyboard or []
    scene_to_slot = {
        str(scene.get("id", "")): str(scene.get("slotId", ""))
        for scene in scenes
        if scene.get("id") and scene.get("slotId")
    }
    resolved: list[str] = []
    for intent in intents:
        resolved.extend(_slot_ids_from_intent(intent))
        for scene_id in _scene_ids_from_intent(intent):
            slot_id = scene_to_slot.get(scene_id)
            if slot_id:
                resolved.append(slot_id)
    return list(dict.fromkeys(resolved))


def resolve_affected_scene_ids(intents: list[dict[str, Any]]) -> list[str]:
    affected: list[str] = []
    for intent in intents:
        affected.extend(_scene_ids_from_intent(intent))
    return list(dict.fromkeys(affected))


def _intent_requires_material_regen(intent: dict[str, Any]) -> bool:
    params = intent.get("params") if isinstance(intent.get("params"), dict) else {}
    if bool(params.get("requiresMaterialRegen")):
        return True
    tool = str(intent.get("executionTool") or "")
    if tool in _SCOPED_MATERIAL_TOOLS:
        return True
    return False


def infer_material_scope(
    intents: list[dict[str, Any]],
    *,
    storyboard: list[dict[str, Any]] | None = None,
) -> MaterialScope:
    if not intents:
        return "all"

    tools = {str(intent.get("executionTool") or "") for intent in intents}
    operations = {str(intent.get("operation", "")) for intent in intents}

    if tools & _ALL_MATERIAL_TOOLS or operations & {
        "adjust_hook",
        "reorder_selling_points",
    }:
        return "all"

    if any(_intent_requires_material_regen(intent) for intent in intents):
        slot_ids = resolve_slot_ids_from_intents(intents, storyboard=storyboard)
        return "scoped" if slot_ids else "all"

    if "packaging_scene_patch" in operations or "packaging_scene_patch" in tools:
        return "none"

    if operations <= {"change_packaging_style", "reduce_subtitles", "increase_subtitles", "subtitle_patch", "adjust_cta"}:
        if not any(_intent_requires_material_regen(intent) for intent in intents):
            return "none"

    if tools == {"packaging_agent"} or (
        operations <= {"change_packaging_style"} and not any(_intent_requires_material_regen(intent) for intent in intents)
    ):
        return "none"

    return "all"


def material_scope_preserves_generated(material_scope: MaterialScope) -> bool:
    return material_scope in {"none", "scoped"}
