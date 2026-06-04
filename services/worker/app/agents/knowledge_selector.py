from __future__ import annotations

from typing import Any

from app.agents.runner import AgentRunner
from app.runtime.task_context import TaskContext


TASK_KEY = "knowledge_selector"
SCHEMA_NAME = "knowledge-selector-output"


def run_knowledge_selector(
    runner: AgentRunner,
    *,
    brief: dict[str, Any],
    candidates: list[dict[str, Any]],
    context: TaskContext,
    progress: int = 20,
) -> dict[str, Any]:
    index_cards = [
        {
            "id": item.get("entryId") or item.get("id"),
            "title": (item.get("entry") or item).get("title"),
            "summary": (item.get("entry") or item).get("summary"),
            "category": (item.get("entry") or item).get("category"),
            "style": (item.get("entry") or item).get("style"),
            "slotPattern": (item.get("entry") or item).get("slotPattern"),
            "hookType": (item.get("entry") or item).get("hookType"),
            "score": item.get("score"),
        }
        for item in candidates
    ]
    return runner.run(
        "knowledge_selector",
        task=TASK_KEY,
        schema_name=SCHEMA_NAME,
        inputs={"userBrief": brief, "candidates": index_cards},
        context=context,
        progress=progress,
    )
