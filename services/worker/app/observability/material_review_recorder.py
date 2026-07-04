from __future__ import annotations

import json
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from app.agents.prompt_loader import PromptLoader
from app.agents.runner import AgentRunner
from app.gateway.model_gateway import ModelGateway
from app.observability.gateway_context import attach_gateway_observability, resolve_profile_model
from app.observability.sink import ObservabilitySink, build_observability_sink
from app.runtime.agent_run_store import AgentRunLog
from app.runtime.task_context import TaskContext
from app.tools.llm_tool import LLMTool

MaterialReviewTraceRoute = Literal["video", "frames", "text_only", "skipped", "hard_gate"]

MATERIAL_REVIEWER_AGENT = "material_reviewer"


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def acp_parent_observability_run_id() -> str | None:
    import os

    raw = os.environ.get("VM_ACP_OBSERVABILITY_RUN_ID", "").strip()
    return raw or None


def setup_material_review_observability(
    *,
    storage_root: Path,
    project_id: str,
    task_id: str | None,
    generation_id: str,
    slot_id: str,
    gateway: ModelGateway | None = None,
    sink: ObservabilitySink | None = None,
) -> tuple[ModelGateway | None, ObservabilitySink]:
    resolved_sink = sink or build_observability_sink(storage_root)
    if gateway is None:
        return None, resolved_sink

    ctx = attach_gateway_observability(
        gateway,
        sink=resolved_sink,
        project_id=project_id,
        task_id=task_id,
        generation_id=generation_id,
    )
    ctx.slot_id = slot_id
    ctx.agent_name = MATERIAL_REVIEWER_AGENT
    return gateway, resolved_sink


def build_material_review_runner(
    *,
    gateway: ModelGateway,
    sink: ObservabilitySink,
) -> AgentRunner:
    llm = LLMTool(fixture_mode=False, gateway=gateway)
    model_name = resolve_profile_model(gateway, "text")
    return AgentRunner(
        llm=llm,
        prompt_loader=PromptLoader(),
        observability_sink=sink,
        model_name=model_name,
    )


def material_review_trace_route(route: str) -> MaterialReviewTraceRoute:
    if route == "vision":
        return "frames"
    if route in {"video", "text_only", "skipped", "hard_gate"}:
        return route  # type: ignore[return-value]
    return "text_only"


def build_material_review_trace(
    *,
    route: str,
    model_call_id: str | None = None,
    agent_run_id: str | None = None,
    prompt_version: str | None = None,
    parent_observability_run_id: str | None = None,
) -> dict[str, Any]:
    trace: dict[str, Any] = {
        "reviewRoute": material_review_trace_route(route),
    }
    if model_call_id:
        trace["modelCallId"] = model_call_id
    if agent_run_id:
        trace["agentRunId"] = agent_run_id
    if prompt_version:
        trace["promptVersion"] = prompt_version
    if parent_observability_run_id:
        trace["parentObservabilityRunId"] = parent_observability_run_id
    return trace


def resolve_material_reviewer_prompt_version() -> str:
    try:
        return PromptLoader().version(MATERIAL_REVIEWER_AGENT)
    except FileNotFoundError:
        return "unknown"


def read_last_model_call_id(gateway: ModelGateway | None) -> str | None:
    if gateway is None:
        return None
    observability = getattr(gateway, "observability", None)
    if observability is None:
        return None
    raw = getattr(observability, "last_model_call_id", None)
    return str(raw) if raw else None


def set_material_review_slot_context(gateway: ModelGateway | None, slot_id: str) -> None:
    if gateway is None:
        return
    observability = getattr(gateway, "observability", None)
    if observability is not None:
        observability.slot_id = slot_id
        observability.agent_name = MATERIAL_REVIEWER_AGENT


def record_material_reviewer_agent_run(
    *,
    sink: ObservabilitySink,
    project_id: str,
    task_id: str | None,
    generation_id: str,
    route: str,
    slot_id: str,
    agent_review_round: int,
    payload_keys: list[str],
    output_valid: bool,
    latency_ms: float,
    model: str,
    token_usage: dict[str, float] | None = None,
    validation_errors: list[str] | None = None,
    run_id: str | None = None,
) -> str:
    agent_run_id = run_id or str(uuid.uuid4())
    input_summary = json.dumps(
        {
            "agent": MATERIAL_REVIEWER_AGENT,
            "route": material_review_trace_route(route),
            "slotId": slot_id,
            "agentReviewRound": agent_review_round,
            "payloadKeys": sorted(payload_keys),
        },
        ensure_ascii=False,
    )[:500]
    payload = AgentRunLog(
        agent_name=MATERIAL_REVIEWER_AGENT,
        prompt_version=resolve_material_reviewer_prompt_version(),
        model=model,
        task=MATERIAL_REVIEWER_AGENT,
        input_summary=input_summary,
        output_valid=output_valid,
        latency_ms=latency_ms,
        task_id=task_id,
        generation_id=generation_id,
        validation_errors=list(validation_errors or []),
        token_usage=token_usage,
        run_id=agent_run_id,
    ).to_payload()
    payload["projectId"] = project_id
    sink.record_agent_run(payload)
    return agent_run_id


def record_material_review_tool_run(
    *,
    sink: ObservabilitySink,
    project_id: str,
    task_id: str | None,
    generation_id: str,
    slot_id: str,
    preview_path: Path | str,
    ok: bool,
    report: dict[str, Any] | None = None,
    error: dict[str, Any] | None = None,
    parent_observability_run_id: str | None = None,
    latency_ms: float = 0.0,
) -> str:
    from app.observability.capture import prepare_payload, resolve_observability_capture

    tool_run_id = f"review_material_preview-{uuid.uuid4()}"
    trace = report.get("trace") if isinstance(report, dict) else None
    output_summary: dict[str, Any] = {"ok": ok}
    if isinstance(report, dict):
        output_summary.update(
            {
                "approved": report.get("approved"),
                "issuesCount": len(report.get("issues") or []),
            }
        )
        if isinstance(trace, dict):
            if trace.get("modelCallId"):
                output_summary["modelCallId"] = trace["modelCallId"]
            if trace.get("agentRunId"):
                output_summary["agentRunId"] = trace["agentRunId"]
    if error:
        output_summary["error"] = error

    capture = resolve_observability_capture()
    metadata: dict[str, Any] = {"eventKind": "material_review_tool"}
    if parent_observability_run_id:
        metadata["parentObservabilityRunId"] = parent_observability_run_id

    payload: dict[str, Any] = {
        "id": tool_run_id,
        "projectId": project_id,
        "agentName": MATERIAL_REVIEWER_AGENT,
        "toolName": "review_material_preview",
        "latencyMs": round(latency_ms, 3),
        "createdAt": _utc_now_iso(),
        "slotId": slot_id,
        "input": prepare_payload(
            {
                "slotId": slot_id,
                "generationId": generation_id,
                "previewPath": str(preview_path),
            },
            capture=capture,
        ),
        "output": prepare_payload(output_summary, capture=capture),
        "metadata": metadata,
    }
    if task_id:
        payload["taskId"] = task_id
    if generation_id:
        payload["generationId"] = generation_id
    sink.record_tool_run(payload)
    return tool_run_id


class MaterialReviewLlmSession:
    """Tracks one material review LLM invocation for agent-run + trace capture."""

    def __init__(
        self,
        *,
        sink: ObservabilitySink | None,
        gateway: ModelGateway | None,
        project_id: str,
        task_id: str | None,
        generation_id: str,
        slot_id: str,
        route: str,
        agent_review_round: int,
        payload_keys: list[str],
    ) -> None:
        self.sink = sink
        self.gateway = gateway
        self.project_id = project_id
        self.task_id = task_id
        self.generation_id = generation_id
        self.slot_id = slot_id
        self.route = route
        self.agent_review_round = agent_review_round
        self.payload_keys = payload_keys
        self._started = time.perf_counter()
        self.output_valid = True
        self.validation_errors: list[str] = []
        self.agent_run_id: str | None = None
        self.model_call_id: str | None = None

    def finish(self) -> dict[str, Any]:
        self.model_call_id = read_last_model_call_id(self.gateway)
        prompt_version = resolve_material_reviewer_prompt_version()
        if self.sink is not None and self.route in {"video", "vision", "text_only"}:
            profile = "video_understanding" if self.route == "video" else "vision" if self.route == "vision" else "text"
            model = "unknown"
            token_usage = None
            if self.gateway is not None:
                model = resolve_profile_model(self.gateway, profile)
                token_usage = getattr(self.gateway, "last_token_usage", None)
            self.agent_run_id = record_material_reviewer_agent_run(
                sink=self.sink,
                project_id=self.project_id,
                task_id=self.task_id,
                generation_id=self.generation_id,
                route=self.route,
                slot_id=self.slot_id,
                agent_review_round=self.agent_review_round,
                payload_keys=self.payload_keys,
                output_valid=self.output_valid,
                latency_ms=(time.perf_counter() - self._started) * 1000,
                model=model,
                token_usage=token_usage if isinstance(token_usage, dict) else None,
                validation_errors=self.validation_errors,
            )
        return build_material_review_trace(
            route=self.route,
            model_call_id=self.model_call_id,
            agent_run_id=self.agent_run_id,
            prompt_version=prompt_version,
            parent_observability_run_id=acp_parent_observability_run_id(),
        )

    def fail(self, errors: list[str]) -> dict[str, Any]:
        self.output_valid = False
        self.validation_errors = errors
        return self.finish()


def noop_task_context(
    *,
    task_id: str,
    project_id: str,
    storage_root: Path,
) -> TaskContext:
    return TaskContext(
        task_id=task_id,
        project_id=project_id,
        storage_root=storage_root,
    )
