from __future__ import annotations

from typing import Any

from app.agents.runner import AgentRunner
from app.runtime.task_context import TaskContext
from app.stock.stock_query_builder import build_deterministic_stock_query

TASK_KEY = "stock_query_author"
SCHEMA_NAME = "stock-search-query"


def run_stock_query_author(
    runner: AgentRunner,
    *,
    slot: dict[str, Any],
    gap_item: dict[str, Any],
    storyboard_scene: dict[str, Any],
    brief: dict[str, Any],
    prefer_video: bool,
    orientation: str | None,
    context: TaskContext,
    progress: int = 58,
    generation_id: str | None = None,
) -> dict[str, Any]:
    inputs: dict[str, Any] = {
        "slot": slot,
        "gapItem": gap_item,
        "storyboardScene": storyboard_scene,
        "brief": brief,
        "preferVideo": prefer_video,
    }
    if orientation:
        inputs["orientation"] = orientation
    return runner.run(
        TASK_KEY,
        task=TASK_KEY,
        schema_name=SCHEMA_NAME,
        inputs=inputs,
        context=context,
        progress=progress,
        generation_id=generation_id,
    )


def resolve_stock_search_query(
    *,
    slot: dict[str, Any],
    gap_item: dict[str, Any],
    storyboard: list[dict[str, Any]],
    brief: dict[str, Any],
    prefer_video: bool,
    orientation: str | None,
    runner: AgentRunner | None,
    context: TaskContext | None,
    generation_id: str | None = None,
    cached: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if cached and cached.get("primaryQuery"):
        return cached

    scene = next((item for item in storyboard if item.get("slotId") == slot.get("id")), {})
    if runner is not None and context is not None:
        try:
            result = run_stock_query_author(
                runner,
                slot=slot,
                gap_item=gap_item,
                storyboard_scene=scene,
                brief=brief,
                prefer_video=prefer_video,
                orientation=orientation,
                context=context,
                generation_id=generation_id,
            )
            merged = dict(result)
            merged.setdefault("preferVideo", prefer_video)
            if orientation:
                merged.setdefault("orientation", orientation)
            return merged
        except Exception:
            pass

    return build_deterministic_stock_query(
        slot=slot,
        storyboard=storyboard,
        gap_reason=str(gap_item.get("reason", "")),
        brief=brief,
    )
