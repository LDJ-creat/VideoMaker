from __future__ import annotations

from typing import Any

from app.agents.runner import AgentRunner
from app.runtime.task_context import TaskContext


TASK_KEY = "gap_planner"
SCHEMA_NAME = "gap-report"


def run_gap_planner(
    runner: AgentRunner,
    *,
    structure: dict[str, Any],
    inventory: dict[str, Any],
    slot_matches: list[dict[str, Any]],
    context: TaskContext,
    progress: int = 45,
    generation_id: str | None = None,
) -> dict[str, Any]:
    gap_report = runner.run(
        "gap_planner",
        task=TASK_KEY,
        schema_name=SCHEMA_NAME,
        inputs={
            "structure": structure,
            "inventory": inventory,
            "slotMatches": slot_matches,
        },
        context=context,
        progress=progress,
        generation_id=generation_id,
    )
    # slot_mapper output is authoritative; fixture gap_report slotMatches may differ.
    gap_report["slotMatches"] = slot_matches
    return gap_report
