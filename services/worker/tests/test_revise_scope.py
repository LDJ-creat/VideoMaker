from __future__ import annotations

from typing import Any

from app.pipelines.intent_applier import apply_intents_to_context, compute_affected_stages
from app.pipelines.revise_scope import (
    infer_material_scope,
    resolve_slot_ids_from_intents,
)


def _storyboard() -> list[dict[str, Any]]:
    return [
        {"id": "scene-1", "slotId": "slot-1", "startSec": 0, "endSec": 3},
        {"id": "scene-6", "slotId": "slot-6", "startSec": 15, "endSec": 18},
    ]


def test_change_packaging_style_excludes_material_stage() -> None:
    intents = [
        {
            "target": "generation_plan.packaging",
            "operation": "change_packaging_style",
            "params": {"style": "minimal"},
            "rationale": "全片包装",
            "executionTool": "packaging_agent",
        }
    ]
    stages = compute_affected_stages(intents)
    assert "generating_material" not in stages
    assert stages == ["planning_completion", "building_timeline", "rendering"]


def test_material_regen_scoped_scope() -> None:
    intents = [
        {
            "target": "generation_plan.storyboard",
            "operation": "change_packaging_style",
            "params": {"requiresMaterialRegen": True, "sceneId": "scene-6"},
            "rationale": "最后一镜画面背景",
            "executionTool": "material_regen",
            "sceneIds": ["scene-6"],
        }
    ]
    context = apply_intents_to_context(intents, source_plan={"storyboard": _storyboard()})
    assert context.material_scope == "scoped"
    assert context.affected_slot_ids == ["slot-6"]
    assert context.preserve_generated is True
    assert context.rerun_storyboard is False
    assert context.rerun_packaging is False
    assert "generating_material" in compute_affected_stages(intents)


def test_packaging_scene_patch_material_scope_none() -> None:
    intents = [
        {
            "target": "generation_plan.packaging",
            "operation": "packaging_scene_patch",
            "params": {"sceneId": "scene-6", "backgroundPreset": "dark"},
            "rationale": "最后一镜标题卡背景",
            "executionTool": "packaging_scene_patch",
            "sceneIds": ["scene-6"],
        }
    ]
    context = apply_intents_to_context(intents, source_plan={"storyboard": _storyboard()})
    assert context.material_scope == "none"
    assert infer_material_scope(intents, storyboard=_storyboard()) == "none"
    assert resolve_slot_ids_from_intents(intents, storyboard=_storyboard()) == ["slot-6"]
