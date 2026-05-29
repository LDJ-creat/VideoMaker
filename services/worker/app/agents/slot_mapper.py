from __future__ import annotations

from typing import Any

from app.agents.runner import AgentRunner
from app.runtime.task_context import TaskContext
from app.validation.schema_loader import validate_contract


TASK_KEY = "slot_mapper"


def _assert_slot_matches(payload: dict[str, Any]) -> dict[str, Any]:
    slot_matches = payload.get("slotMatches")
    if not isinstance(slot_matches, list):
        raise ValueError("slot_mapper output must include slotMatches array")
    for match in slot_matches:
        if not isinstance(match, dict):
            raise ValueError("slotMatches items must be objects")
        probe = {
            "id": "gap-probe",
            "projectId": "probe",
            "structureId": "probe",
            "inventoryId": "probe",
            "slotMatches": [match],
            "missingSlots": [],
            "weakSlots": [],
            "summary": "probe",
        }
        validation = validate_contract("gap-report", probe)
        if not validation.valid:
            raise ValueError(f"Invalid slot match: {validation.errors}")
    return payload


def run_slot_mapper(
    runner: AgentRunner,
    *,
    structure: dict[str, Any],
    inventory: dict[str, Any],
    context: TaskContext,
    progress: int = 35,
    generation_id: str | None = None,
) -> list[dict[str, Any]]:
    output = runner.run(
        "slot_mapper",
        task=TASK_KEY,
        schema_name=None,
        inputs={"structure": structure, "inventory": inventory},
        context=context,
        progress=progress,
        generation_id=generation_id,
        post_validate=_assert_slot_matches,
    )
    return output["slotMatches"]
