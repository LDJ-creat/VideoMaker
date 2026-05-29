from __future__ import annotations

from typing import Any

from app.agents.runner import AgentRunner
from app.runtime.task_context import TaskContext


TASK_KEY = "storyboard_writer"


def _assert_storyboard(payload: dict[str, Any]) -> dict[str, Any]:
    storyboard = payload.get("storyboard")
    if not isinstance(storyboard, list):
        raise ValueError("storyboard_writer output must include storyboard array")
    required = {"id", "slotId", "startSec", "endSec", "visual", "script", "source"}
    for scene in storyboard:
        if not isinstance(scene, dict):
            raise ValueError("storyboard items must be objects")
        missing = required - set(scene.keys())
        if missing:
            raise ValueError(f"storyboard scene missing fields: {sorted(missing)}")
    return payload


def run_storyboard_writer(
    runner: AgentRunner,
    *,
    structure: dict[str, Any],
    inventory: dict[str, Any],
    gap_report: dict[str, Any],
    context: TaskContext,
    progress: int = 52,
    generation_id: str | None = None,
) -> list[dict[str, Any]]:
    output = runner.run(
        "storyboard_writer",
        task=TASK_KEY,
        schema_name=None,
        inputs={
            "structure": structure,
            "inventory": inventory,
            "gapReport": gap_report,
        },
        context=context,
        progress=progress,
        generation_id=generation_id,
        post_validate=_assert_storyboard,
    )
    return output["storyboard"]
