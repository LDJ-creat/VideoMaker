from __future__ import annotations

from pathlib import Path
from typing import Any

from app.agents.knowledge_author import run_knowledge_author
from app.agents.runner import AgentRunner
from app.knowledge.skill_writer import write_knowledge_draft
from app.runtime.task_context import TaskContext


def deposit_knowledge_draft(
    runner: AgentRunner,
    *,
    storage_root: Path,
    project_id: str,
    sample_id: str,
    structure: dict[str, Any],
    sample_analysis: dict[str, Any] | None,
    context: TaskContext,
) -> dict[str, Any]:
    skill_output = run_knowledge_author(
        runner,
        structure=structure,
        sample_analysis=sample_analysis,
        context=context,
    )
    uris = write_knowledge_draft(
        storage_root,
        project_id=project_id,
        sample_id=sample_id,
        structure=structure,
        skill_output=skill_output,
    )
    return {"skillOutput": skill_output, "uris": uris}
