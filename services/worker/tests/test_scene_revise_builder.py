from __future__ import annotations



from typing import Any



import pytest



from app.pipelines.intent_applier import apply_intents_to_context

from app.pipelines.revise_scope import infer_material_scope

from app.pipelines.scene_revise_builder import (

    build_scene_revise_intents,

    build_scene_revise_planner_output,

    validate_scene_in_plan,

)





def _source_plan() -> dict[str, Any]:

    return {

        "storyboard": [

            {"id": "scene-1", "slotId": "slot-1", "startSec": 0, "endSec": 3, "script": "a"},

            {"id": "scene-2", "slotId": "slot-2", "startSec": 3, "endSec": 6, "script": "b"},

        ]

    }





def test_validate_scene_in_plan_ok() -> None:

    scene = validate_scene_in_plan(_source_plan(), "scene-2", "slot-2")

    assert scene["slotId"] == "slot-2"





def test_validate_scene_slot_mismatch() -> None:

    with pytest.raises(ValueError, match="slotId mismatch"):

        validate_scene_in_plan(_source_plan(), "scene-2", "slot-1")





def test_edit_mode_intent_and_scope() -> None:

    request = {

        "sceneId": "scene-2",

        "slotId": "slot-2",

        "mode": "edit",

        "instruction": "字幕居中，样式保持不变",

    }

    intents = build_scene_revise_intents(request, source_plan=_source_plan())

    assert len(intents) == 1

    intent = intents[0]

    assert intent["executionTool"] == "material_regen"

    assert intent["params"]["materialEditMode"] == "edit"

    assert intent["params"]["editInstruction"] == "字幕居中，样式保持不变"



    output = build_scene_revise_planner_output(request, source_plan=_source_plan())

    assert output["executionMode"] == "fork"

    assert output["planSource"] == "scene_structured"

    assert output["affectedSlotIds"] == ["slot-2"]



    context = apply_intents_to_context(intents, source_plan=_source_plan())

    assert context.material_scope == "scoped"





def test_full_mode_intent() -> None:

    request = {

        "sceneId": "scene-1",

        "slotId": "slot-1",

        "mode": "full",

        "instruction": "改成赛博朋克风格",

    }

    output = build_scene_revise_planner_output(request, source_plan=_source_plan())

    assert output["executionMode"] == "fork"

    assert output["intents"][0]["params"]["materialEditMode"] == "full"

    assert infer_material_scope(output["intents"], storyboard=_source_plan()["storyboard"]) == "scoped"





def test_missing_instruction_raises() -> None:

    with pytest.raises(ValueError, match="instruction is required"):

        build_scene_revise_intents(

            {"sceneId": "scene-1", "slotId": "slot-1", "mode": "edit", "instruction": "  "},

            source_plan=_source_plan(),

        )





def test_unsupported_mode_raises() -> None:

    with pytest.raises(ValueError, match="Unsupported scene visual edit mode"):

        build_scene_revise_intents(

            {"sceneId": "scene-1", "slotId": "slot-1", "mode": "refresh", "instruction": "x"},

            source_plan=_source_plan(),

        )

