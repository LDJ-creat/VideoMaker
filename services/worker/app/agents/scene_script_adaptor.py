from __future__ import annotations

from typing import Any

from app.agents.runner import AgentRunner
from app.runtime.task_context import TaskContext

TASK_KEY = "scene_script_adaptor"


def _assert_script_adaptor_output(payload: dict[str, Any]) -> dict[str, Any]:
    script = str(payload.get("script") or "").strip()
    master = str(payload.get("masterNarration") or "").strip()
    if not script:
        raise ValueError("scene_script_adaptor output must include non-empty script")
    if not master:
        raise ValueError("scene_script_adaptor output must include non-empty masterNarration")
    forbidden = {"compositionAuthorBrief", "visual", "storyboard"}
    if forbidden.intersection(payload.keys()):
        raise ValueError("scene_script_adaptor must not output brief/visual/storyboard fields")
    result: dict[str, Any] = {"script": script, "masterNarration": master}
    vo_directive = payload.get("voDirective")
    if isinstance(vo_directive, dict) and vo_directive:
        result["voDirective"] = vo_directive
    if isinstance(payload.get("summary"), str) and payload["summary"].strip():
        result["summary"] = payload["summary"].strip()
    return result


def run_scene_script_adaptor(
    runner: AgentRunner,
    *,
    target_slot_id: str,
    scene: dict[str, Any],
    master_narration: str,
    timing: dict[str, Any],
    slot_role: str,
    duration_target_sec: float,
    visual_style_bible: dict[str, Any] | None,
    instruction: str | None,
    context: TaskContext,
    generation_id: str | None = None,
) -> dict[str, Any]:
    return runner.run(
        "scene_script_adaptor",
        task=TASK_KEY,
        schema_name=None,
        inputs={
            "phase": "adapt_script_density",
            "targetSlotId": target_slot_id,
            "scene": scene,
            "masterNarration": master_narration,
            "timing": timing,
            "slotRole": slot_role,
            "durationTargetSec": duration_target_sec,
            "visualStyleBible": visual_style_bible or {},
            "instruction": instruction,
        },
        context=context,
        progress=55,
        generation_id=generation_id,
        post_validate=_assert_script_adaptor_output,
    )
