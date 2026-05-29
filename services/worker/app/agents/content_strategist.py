from __future__ import annotations

from typing import Any

from app.agents.runner import AgentRunner
from app.runtime.task_context import TaskContext


TASK_KEY = "content_strategist"
SCHEMA_NAME = "asset-inventory"


def run_content_strategist(
    runner: AgentRunner,
    *,
    inventory: dict[str, Any],
    context: TaskContext,
    progress: int = 15,
    generation_id: str | None = None,
) -> dict[str, Any]:
    return runner.run(
        "content_strategist",
        task=TASK_KEY,
        schema_name=SCHEMA_NAME,
        inputs={"inventory": inventory},
        context=context,
        progress=progress,
        generation_id=generation_id,
    )
