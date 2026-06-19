from __future__ import annotations

import json
from typing import Any

from app.observability.gateway_context import resolve_profile_model
from app.observability.token_usage import latest_token_usage_from_llm
from app.runtime.agent_run_store import AgentRunLog
from app.runtime.task_context import TaskContext


def record_live_agent_run(
    runner: Any,
    *,
    agent_name: str,
    task: str,
    input_summary: dict[str, Any],
    valid: bool,
    latency_ms: float,
    context: TaskContext,
    generation_id: str | None = None,
    validation_errors: list[str] | None = None,
    profile: str = "text",
) -> None:
    model_name = runner.model_name
    gateway = runner.llm.gateway
    if gateway is not None and not runner.llm.fixture_mode:
        model_name = resolve_profile_model(gateway, profile)

    payload = AgentRunLog(
        agent_name=agent_name,
        prompt_version=runner.prompt_loader.version(agent_name),
        model=model_name,
        task=task,
        input_summary=json.dumps(input_summary, ensure_ascii=False)[:500],
        output_valid=valid,
        latency_ms=latency_ms,
        task_id=context.task_id,
        generation_id=generation_id,
        validation_errors=list(validation_errors or []),
        token_usage=latest_token_usage_from_llm(runner.llm),
    ).to_payload()
    payload["projectId"] = context.project_id
    runner.observability_sink.record_agent_run(payload)
