from __future__ import annotations

from typing import Any

from app.agents.runner import AgentRunner
from app.runtime.task_context import TaskContext


TASK_KEY = "composition_pattern_author"
SCHEMA_NAME = "composition-pattern-promote-output"


def _merge_frontmatter(payload: dict[str, Any], *, slot: dict[str, Any]) -> dict[str, Any]:
    frontmatter = dict(payload.get("frontmatter") or {})
    role = str(slot.get("role") or slot.get("slotId") or "composition")
    if not frontmatter.get("title"):
        frontmatter["title"] = f"{role} 包装动效"
    if not frontmatter.get("category"):
        frontmatter["category"] = "composition"
    if not frontmatter.get("summary"):
        frontmatter["summary"] = f"可复用的 {role} HyperFrames 包装动效"
    if not frontmatter.get("slotRoles"):
        frontmatter["slotRoles"] = [role]
    if not frontmatter.get("motionPattern"):
        frontmatter["motionPattern"] = "custom"
    payload = dict(payload)
    payload["frontmatter"] = frontmatter
    return payload


def run_composition_pattern_author(
    runner: AgentRunner,
    *,
    material_spec: dict[str, Any],
    instance_spec: dict[str, Any],
    slot: dict[str, Any],
    context: TaskContext,
    validation_errors: list[str] | None = None,
    generation_id: str | None = None,
    progress: int = 50,
) -> dict[str, Any]:
    inputs: dict[str, Any] = {
        "materialSpec": material_spec,
        "instanceSpec": instance_spec,
        "slot": slot,
    }
    if validation_errors:
        inputs["validationErrors"] = validation_errors
    output = runner.run(
        "composition_pattern_author",
        task=TASK_KEY,
        schema_name=SCHEMA_NAME,
        inputs=inputs,
        context=context,
        progress=progress,
        generation_id=generation_id,
        post_validate=lambda payload: _merge_frontmatter(payload, slot=slot),
    )
    return output
