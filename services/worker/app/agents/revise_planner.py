from __future__ import annotations

from typing import Any

from app.agents.runner import AgentRunner
from app.runtime.task_context import TaskContext

TASK_KEY = "revise_planner"
SCHEMA_NAME = "revise-planner-output"

__all__ = [
    "TASK_KEY",
    "SCHEMA_NAME",
    "run_revise_planner",
]


def run_revise_planner(
    runner: AgentRunner,
    *,
    instruction: str,
    source_summary: dict[str, Any],
    storyboard_scenes: list[dict[str, Any]] | None = None,
    session_turns: list[dict[str, Any]] | None = None,
    conversation_summary: str | None = None,
    context: TaskContext,
    generation_id: str | None = None,
) -> dict[str, Any]:
    inputs: dict[str, Any] = {
        "instruction": instruction,
        "sourceSummary": source_summary,
    }
    if storyboard_scenes:
        inputs["storyboardScenes"] = storyboard_scenes
    if session_turns:
        inputs["sessionTurns"] = session_turns
    if conversation_summary:
        inputs["conversationSummary"] = conversation_summary
    return runner.run(
        "revise_planner",
        task=TASK_KEY,
        schema_name=SCHEMA_NAME,
        inputs=inputs,
        context=context,
        progress=8,
        generation_id=generation_id,
    )
