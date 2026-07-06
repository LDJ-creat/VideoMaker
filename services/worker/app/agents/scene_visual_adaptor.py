from __future__ import annotations

from typing import Any

from app.agents.runner import AgentRunner
from app.runtime.task_context import TaskContext
from app.validation.schema_loader import validate_contract

TASK_KEY = "scene_visual_adaptor"


def _assert_visual_adaptor_output(payload: dict[str, Any]) -> dict[str, Any]:
    brief = payload.get("compositionAuthorBrief")
    if not isinstance(brief, dict):
        raise ValueError("scene_visual_adaptor output must include compositionAuthorBrief object")
    validation = validate_contract("composition-author-brief", brief)
    if not validation.valid:
        raise ValueError(f"Invalid compositionAuthorBrief: {validation.errors}")
    forbidden = {"script", "masterNarration", "storyboard", "voDirective"}
    if forbidden.intersection(payload.keys()):
        raise ValueError("scene_visual_adaptor must not output script/master/storyboard fields")
    result: dict[str, Any] = {"compositionAuthorBrief": brief}
    if isinstance(payload.get("visual"), str) and payload["visual"].strip():
        result["visual"] = payload["visual"].strip()
    if isinstance(payload.get("summary"), str) and payload["summary"].strip():
        result["summary"] = payload["summary"].strip()
    return result


def run_scene_visual_adaptor(
    runner: AgentRunner,
    *,
    scene: dict[str, Any],
    timing: dict[str, Any],
    slot_role: str,
    visual_style_bible: dict[str, Any] | None,
    structure_slot: dict[str, Any] | None,
    drift_warnings: list[str] | None,
    context: TaskContext,
    generation_id: str | None = None,
) -> dict[str, Any]:
    return runner.run(
        "scene_visual_adaptor",
        task=TASK_KEY,
        schema_name=None,
        inputs={
            "phase": "adapt_visual_timing",
            "scene": scene,
            "timing": timing,
            "slotRole": slot_role,
            "visualStyleBible": visual_style_bible or {},
            "structureSlot": structure_slot or {},
            "driftWarnings": list(drift_warnings or []),
        },
        context=context,
        progress=55,
        generation_id=generation_id,
        post_validate=_assert_visual_adaptor_output,
    )
