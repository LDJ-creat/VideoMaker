from __future__ import annotations

import json
import time
from typing import Any

from app.agents.runner import AgentRunner
from app.gateway.model_gateway import ModelGateway
from app.pipelines.direct_asset_understanding import (
    build_agent_text_message,
    build_media_parts,
)
from app.pipelines.user_brief import normalize_user_brief
from app.runtime.agent_run_store import AgentRunLog
from app.runtime.task_context import TaskContext
from app.tools.llm_tool import LLMToolConfigError, LLMToolValidationError
from app.validation.schema_loader import validate_contract

TASK_KEY = "asset_inventory_analyst"
SCHEMA_NAME = "asset-inventory"
_MAX_REPAIR_ATTEMPTS = 1


def _validate_agent_output(payload: dict[str, Any]) -> dict[str, Any]:
    probe = {
        "id": "inventory-probe",
        "projectId": "probe",
        "userBrief": normalize_user_brief(
            {
                "sellingPoints": [],
                "mustMention": [],
                "avoidMention": [],
            }
        ),
        "assets": [],
        "extractedFacts": list(payload.get("extractedFacts") or []),
        "candidateMoments": list(payload.get("candidateMoments") or []),
    }
    validation = validate_contract(SCHEMA_NAME, probe)
    if not validation.valid:
        raise LLMToolValidationError(
            f"LLM output failed schema validation for '{SCHEMA_NAME}'",
            raw_output=json.dumps(payload, ensure_ascii=False),
            validation_errors=validation.errors,
        )
    return payload


def _run_live_batch(
    runner: AgentRunner,
    *,
    system_prompt: str,
    text_message: dict[str, Any],
    packed_items: list[Any],
    context: TaskContext,
) -> dict[str, Any]:
    gateway = runner.llm.gateway
    if gateway is None:
        raise LLMToolConfigError("No ModelGateway configured for live mode")

    media_parts = build_media_parts(packed_items)
    messages = ModelGateway.build_asset_inventory_messages(
        system_prompt=system_prompt,
        text_message=text_message,
        media_parts=media_parts,
    )
    return gateway.complete_json_messages(messages, profile="video_understanding")


def run_asset_inventory_analyst(
    runner: AgentRunner,
    *,
    inventory: dict[str, Any],
    packed_items: list[Any],
    context: TaskContext,
    generation_id: str | None = None,
    video_structure: dict[str, Any] | None = None,
    progress: int = 15,
) -> dict[str, Any]:
    text_message = build_agent_text_message(
        inventory=inventory,
        packed_items=packed_items,
        video_structure=video_structure,
    )
    repair_errors: list[str] | None = None

    for attempt in range(_MAX_REPAIR_ATTEMPTS + 1):
        attempt_message = dict(text_message)
        if repair_errors:
            attempt_message["validationErrors"] = repair_errors
        started = time.perf_counter()
        valid = True
        errors: list[str] = []
        try:
            if runner.llm.fixture_mode:
                output = runner.run(
                    "asset_inventory_analyst",
                    task=TASK_KEY,
                    schema_name=None,
                    inputs=attempt_message,
                    context=context,
                    progress=progress,
                    generation_id=generation_id,
                    post_validate=_validate_agent_output,
                )
            else:
                system_prompt = runner.prompt_loader.load("asset_inventory_analyst")
                output = _run_live_batch(
                    runner,
                    system_prompt=system_prompt,
                    text_message=attempt_message,
                    packed_items=packed_items,
                    context=context,
                )
                output = _validate_agent_output(output)
            return output
        except LLMToolValidationError as exc:
            valid = False
            errors = [str(item) for item in exc.validation_errors]
            if attempt >= _MAX_REPAIR_ATTEMPTS:
                raise
            repair_errors = errors
        finally:
            latency_ms = (time.perf_counter() - started) * 1000
            payload = AgentRunLog(
                agent_name="asset_inventory_analyst",
                prompt_version=runner.prompt_loader.version("asset_inventory_analyst"),
                model=runner.model_name,
                task=TASK_KEY,
                input_summary=json.dumps(
                    {
                        "agent": "asset_inventory_analyst",
                        "assetCount": len(packed_items),
                    },
                    ensure_ascii=False,
                )[:500],
                output_valid=valid,
                latency_ms=latency_ms,
                task_id=context.task_id,
                validation_errors=errors,
            ).to_payload()
            payload["projectId"] = context.project_id
            if generation_id:
                payload["generationId"] = generation_id
            runner.observability_sink.record_agent_run(payload)

    raise RuntimeError("asset_inventory_analyst repair loop exited without result")
