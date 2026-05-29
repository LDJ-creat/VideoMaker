from __future__ import annotations

from typing import Any

from app.agents.runner import AgentRunner
from app.runtime.task_context import TaskContext


TASK_KEY = "structure_analyst"
SCHEMA_NAME = "video-structure"


def run_structure_analyst(
    runner: AgentRunner,
    *,
    analysis: dict[str, Any],
    context: TaskContext,
    project_id: str,
    source_video_id: str,
    progress: int = 92,
) -> dict[str, Any]:
    structure = runner.run(
        "structure_analyst",
        task=TASK_KEY,
        schema_name=SCHEMA_NAME,
        inputs={"analysis": analysis, "projectId": project_id, "sourceVideoId": source_video_id},
        context=context,
        progress=progress,
    )
    structure.setdefault("projectId", project_id)
    structure.setdefault("sourceVideoId", source_video_id)
    return structure
