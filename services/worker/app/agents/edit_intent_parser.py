from __future__ import annotations

from typing import Any

from app.agents.runner import AgentRunner
from app.pipelines.intent_applier import build_source_summary, parse_edit_intent_for_api
from app.runtime.task_context import TaskContext

TASK_KEY = "edit_intent_parser"
SCHEMA_NAME = "edit-intent"

__all__ = [
    "TASK_KEY",
    "SCHEMA_NAME",
    "build_source_summary",
    "parse_edit_intent_for_api",
    "run_edit_intent_parser",
]


def run_edit_intent_parser(
    runner: AgentRunner,
    *,
    instruction: str,
    source_summary: dict[str, Any],
    context: TaskContext,
    generation_id: str | None = None,
) -> dict[str, Any]:
    return runner.run(
        "edit_intent_parser",
        task=TASK_KEY,
        schema_name=SCHEMA_NAME,
        inputs={
            "instruction": instruction,
            "sourceSummary": source_summary,
        },
        context=context,
        progress=8,
        generation_id=generation_id,
    )
