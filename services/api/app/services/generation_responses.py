from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from app.services.variant_registry import default_variant_ids


def build_generation_plan_response(record: dict[str, Any]) -> dict[str, Any]:
    plan = record.get("plan")
    if plan is None:
        raise HTTPException(status_code=404, detail="Generation plan not ready")

    response: dict[str, Any] = {**plan, "id": record["id"]}
    if record.get("gapReport"):
        response["gapReport"] = record["gapReport"]
    return response


def build_latest_generations_response(records: list[dict[str, Any]]) -> dict[str, Any]:
    order = default_variant_ids()
    order_index = {variant_id: index for index, variant_id in enumerate(order)}

    def sort_key(record: dict[str, Any]) -> tuple[int, str]:
        variant = str(record.get("variant") or "default")
        return (order_index.get(variant, len(order)), variant)

    generations: list[dict[str, Any]] = []
    for record in sorted(records, key=sort_key):
        plan = build_generation_plan_response(record)
        variant = record.get("variant") or plan.get("variant") or "default"
        generations.append(
            {
                "generationId": record["id"],
                "variant": variant,
                "plan": plan,
            }
        )
    return {"generations": generations}
