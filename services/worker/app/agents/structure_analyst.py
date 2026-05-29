from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from app.agents.runner import AgentRunner
from app.agents.structure_inputs import build_structure_analyst_inputs
from app.gateway.model_gateway import ModelGateway
from app.runtime.agent_run_store import AgentRunLog
from app.runtime.task_context import TaskContext
from app.tools.llm_tool import LLMToolConfigError, LLMToolValidationError
from app.validation.schema_loader import validate_contract
from app.validation.structure_validator import StructureValidationError, validate_video_structure


TASK_KEY = "structure_analyst"
SCHEMA_NAME = "video-structure"
_MAX_REPAIR_ATTEMPTS = 1


def _validate_schema(payload: dict[str, Any]) -> dict[str, Any]:
    validation = validate_contract(SCHEMA_NAME, payload)
    if validation.valid:
        return payload
    raise LLMToolValidationError(
        f"LLM output failed schema validation for '{SCHEMA_NAME}'",
        raw_output=json.dumps(payload, ensure_ascii=False),
        validation_errors=validation.errors,
    )


def _post_validate(
    structure: dict[str, Any],
    *,
    reference_shots: list[dict[str, Any]],
) -> dict[str, Any]:
    return validate_video_structure(structure, reference_shots=reference_shots)


def _run_live(
    runner: AgentRunner,
    *,
    system_prompt: str,
    agent_inputs: dict[str, Any],
    keyframes: list[dict[str, Any]],
    reference_shots: list[dict[str, Any]],
    context: TaskContext,
    progress: int,
) -> dict[str, Any]:
    gateway = runner.llm.gateway
    if gateway is None:
        raise LLMToolConfigError("No ModelGateway configured for live mode")

    context.emit_event(
        stage="running_agent",
        progress=progress,
        message="Running structure_analyst",
    )
    started = time.perf_counter()
    text_payload = {"systemPrompt": system_prompt, "inputs": agent_inputs}
    profile = "vision" if keyframes else "text"
    messages = ModelGateway.build_structure_messages(
        system_prompt=system_prompt,
        text_payload=text_payload,
        keyframes=keyframes if keyframes else None,
    )
    output: dict[str, Any] | None = None
    valid = True
    errors: list[str] = []
    try:
        payload = gateway.complete_json_messages(messages, profile=profile)
        output = _validate_schema(payload)
        output = _post_validate(output, reference_shots=reference_shots)
    except (LLMToolValidationError, StructureValidationError, LLMToolConfigError) as exc:
        valid = False
        errors = [str(exc)]
        raise
    finally:
        latency_ms = (time.perf_counter() - started) * 1000
        runner.run_store.record(
            project_id=context.project_id,
            log=AgentRunLog(
                agent_name="structure_analyst",
                prompt_version=runner.prompt_loader.version("structure_analyst"),
                model=runner.model_name,
                task=TASK_KEY,
                input_summary=json.dumps(
                    {"agent": "structure_analyst", "vision": bool(keyframes)},
                    ensure_ascii=False,
                )[:500],
                output_valid=valid,
                latency_ms=latency_ms,
                task_id=context.task_id,
                validation_errors=errors,
            ),
        )
    assert output is not None
    return output


def run_structure_analyst(
    runner: AgentRunner,
    *,
    analysis: dict[str, Any],
    context: TaskContext,
    project_id: str,
    source_video_id: str,
    analysis_root: Path | str | None = None,
    progress: int = 92,
) -> dict[str, Any]:
    root = Path(analysis_root) if analysis_root is not None else None
    require_keyframes = root is not None and not runner.llm.fixture_mode
    packaged = build_structure_analyst_inputs(
        analysis,
        analysis_root=root,
        require_keyframe_files=require_keyframes,
    )
    keyframes = list(packaged.get("keyframes", []))
    reference_shots = list(packaged.get("shots", []))
    agent_inputs: dict[str, Any] = {
        "projectId": project_id,
        "sourceVideoId": source_video_id,
        "analysis": packaged,
    }

    repair_errors: list[str] | None = None
    for attempt in range(_MAX_REPAIR_ATTEMPTS + 1):
        attempt_inputs = dict(agent_inputs)
        if repair_errors:
            attempt_inputs["validationErrors"] = repair_errors
        attempt_keyframes = keyframes if not repair_errors else []

        try:
            if runner.llm.fixture_mode:
                structure = runner.run(
                    "structure_analyst",
                    task=TASK_KEY,
                    schema_name=SCHEMA_NAME,
                    inputs=attempt_inputs,
                    context=context,
                    progress=progress,
                    post_validate=lambda output: _post_validate(
                        output,
                        reference_shots=reference_shots,
                    ),
                )
            else:
                system_prompt = runner.prompt_loader.load("structure_analyst")
                structure = _run_live(
                    runner,
                    system_prompt=system_prompt,
                    agent_inputs=attempt_inputs,
                    keyframes=attempt_keyframes,
                    reference_shots=reference_shots,
                    context=context,
                    progress=progress,
                )
            structure.setdefault("projectId", project_id)
            structure.setdefault("sourceVideoId", source_video_id)
            return structure
        except StructureValidationError as exc:
            if attempt >= _MAX_REPAIR_ATTEMPTS:
                raise
            repair_errors = exc.errors

    raise AssertionError("structure analyst repair loop exited without result")
