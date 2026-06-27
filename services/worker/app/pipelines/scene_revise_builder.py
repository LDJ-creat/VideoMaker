from __future__ import annotations



from typing import Any



from app.pipelines.revise_plan_builder import build_planner_output_from_intents



SCENE_VISUAL_EDIT_MODES = frozenset({"edit", "full"})



_MODE_LABELS: dict[str, str] = {

    "edit": "微调修改",

    "full": "完全重生成",

}





def validate_scene_in_plan(

    source_plan: dict[str, Any],

    scene_id: str,

    slot_id: str,

) -> dict[str, Any]:

    storyboard = source_plan.get("storyboard")

    if not isinstance(storyboard, list):

        raise ValueError("Source plan has no storyboard")

    for scene in storyboard:

        if not isinstance(scene, dict):

            continue

        if str(scene.get("id", "")) != scene_id:

            continue

        resolved_slot = str(scene.get("slotId", ""))

        if resolved_slot != slot_id:

            raise ValueError(f"slotId mismatch for scene {scene_id}: expected {resolved_slot}, got {slot_id}")

        return scene

    raise ValueError(f"sceneId not found in storyboard: {scene_id}")





def _scene_index(source_plan: dict[str, Any], scene_id: str) -> int:

    storyboard = source_plan.get("storyboard")

    if not isinstance(storyboard, list):

        return -1

    for index, scene in enumerate(storyboard):

        if isinstance(scene, dict) and str(scene.get("id", "")) == scene_id:

            return index

    return -1





def build_scene_revise_instruction_summary(

    request: dict[str, Any],

    *,

    source_plan: dict[str, Any],

) -> str:

    instruction = str(request.get("instruction") or "").strip()

    if instruction:

        return instruction

    mode = str(request.get("mode") or "")

    scene_id = str(request.get("sceneId") or "")

    slot_id = str(request.get("slotId") or "")

    index = _scene_index(source_plan, scene_id)

    label = _MODE_LABELS.get(mode, mode)

    scene_num = index + 1 if index >= 0 else "?"

    return f"第 {scene_num} 镜 · {label}（{slot_id}）"





def build_scene_revise_intents(

    request: dict[str, Any],

    *,

    source_plan: dict[str, Any],

) -> list[dict[str, Any]]:

    mode = str(request.get("mode") or "")

    if mode not in SCENE_VISUAL_EDIT_MODES:

        raise ValueError(f"Unsupported scene visual edit mode: {mode}")



    instruction = str(request.get("instruction") or "").strip()

    if not instruction:

        raise ValueError("instruction is required")



    scene_id = str(request.get("sceneId") or "")

    slot_id = str(request.get("slotId") or "")

    if not scene_id or not slot_id:

        raise ValueError("sceneId and slotId are required")



    validate_scene_in_plan(source_plan, scene_id, slot_id)

    summary = build_scene_revise_instruction_summary(request, source_plan=source_plan)



    return [

        {

            "target": "generation_plan.storyboard",

            "operation": "change_packaging_style",

            "executionTool": "material_regen",

            "scope": "scene",

            "sceneIds": [scene_id],

            "slotIds": [slot_id],

            "params": {

                "sceneId": scene_id,

                "slotId": slot_id,

                "materialEditMode": mode,

                "editInstruction": instruction,

                "requiresMaterialRegen": True,

            },

            "rationale": summary or f"修改 {slot_id} 画面",

        }

    ]





def build_scene_revise_planner_output(

    request: dict[str, Any],

    *,

    source_plan: dict[str, Any],

) -> dict[str, Any]:

    intents = build_scene_revise_intents(request, source_plan=source_plan)

    instruction = build_scene_revise_instruction_summary(request, source_plan=source_plan)

    output = build_planner_output_from_intents(intents, instruction, source_plan=source_plan)

    output["planSource"] = "scene_structured"

    output["conversationSummary"] = instruction

    return output

