from __future__ import annotations

from typing import Any

from app.agents.runner import AgentRunner
from app.runtime.task_context import TaskContext
from app.validation.schema_loader import validate_contract


TASK_KEY = "packaging_designer"


def _assert_packaging_plan(payload: dict[str, Any]) -> dict[str, Any]:
    packaging_plan = payload.get("packagingPlan")
    if not isinstance(packaging_plan, dict):
        raise ValueError("packaging_designer output must include packagingPlan object")
    probe = {
        "id": "plan-probe",
        "projectId": "probe",
        "structureId": "probe",
        "inventoryId": "probe",
        "gapReportId": "probe",
        "variant": "default",
        "storyboard": [],
        "timeline": {"durationSec": 0.0, "tracks": []},
        "packagingPlan": packaging_plan,
        "completionActions": [],
    }
    validation = validate_contract("generation-plan", probe)
    if not validation.valid:
        raise ValueError(f"Invalid packagingPlan: {validation.errors}")
    return payload


def run_packaging_designer(
    runner: AgentRunner,
    *,
    structure: dict[str, Any],
    storyboard: list[dict[str, Any]],
    context: TaskContext,
    progress: int = 58,
    generation_id: str | None = None,
) -> dict[str, Any]:
    output = runner.run(
        "packaging_designer",
        task=TASK_KEY,
        schema_name=None,
        inputs={"structure": structure, "storyboard": storyboard},
        context=context,
        progress=progress,
        generation_id=generation_id,
        post_validate=_assert_packaging_plan,
    )
    return output["packagingPlan"]
