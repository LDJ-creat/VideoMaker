from __future__ import annotations

from typing import Any

from app.agents.runner import AgentRunner
from app.runtime.task_context import TaskContext


TASK_KEY = "structure_critic"
SCHEMA_NAME = "structure-critic-output"


def run_structure_critic(
    runner: AgentRunner,
    *,
    structure: dict[str, Any],
    context: TaskContext,
    progress: int = 94,
) -> dict[str, Any]:
    inputs = {
        "videoStructure": structure,
        "locale": (structure.get("analysisQuality") or {}).get("locale", "zh"),
    }
    return runner.run(
        "structure_critic",
        task=TASK_KEY,
        schema_name=SCHEMA_NAME,
        inputs=inputs,
        context=context,
        progress=progress,
    )
