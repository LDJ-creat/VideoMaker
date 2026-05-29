from __future__ import annotations

from typing import Any

from fastapi import HTTPException


def build_generation_plan_response(record: dict[str, Any]) -> dict[str, Any]:
    plan = record.get("plan")
    if plan is None:
        raise HTTPException(status_code=404, detail="Generation plan not ready")

    response: dict[str, Any] = {**plan, "id": record["id"]}
    if record.get("gapReport"):
        response["gapReport"] = record["gapReport"]
    return response
