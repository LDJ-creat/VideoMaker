from __future__ import annotations

import logging
import os
import json
from typing import Any

from app.observability.capture import (
    capture_enabled_for_langfuse,
    prepare_payload,
    resolve_langfuse_capture,
)
from app.observability.langfuse_config import resolve_langfuse_client_kwargs

logger = logging.getLogger(__name__)


def _parse_agent_summary_metadata(input_summary: Any) -> dict[str, Any]:
    if not isinstance(input_summary, str) or not input_summary.strip():
        return {}
    try:
        parsed = json.loads(input_summary)
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    metadata: dict[str, Any] = {}
    for key in ("backend", "acpAgent", "acpTraceDir", "slotRole", "slotId", "reactTraceDir"):
        if key in parsed:
            metadata[key] = parsed[key]
    return metadata


def _normalize_token_usage(usage: dict[str, Any]) -> dict[str, int]:
    details: dict[str, int] = {}
    prompt = usage.get("prompt")
    if prompt is None:
        prompt = usage.get("input")
    completion = usage.get("completion")
    if completion is None:
        completion = usage.get("output")
    if prompt is not None:
        details["input"] = int(prompt)
    if completion is not None:
        details["output"] = int(completion)
    total = usage.get("total")
    if total is not None:
        details["total"] = int(total)
    elif details:
        details["total"] = details.get("input", 0) + details.get("output", 0)
    return details


class LangfuseSink:
    """Optional Langfuse export. Disabled unless LANGFUSE_ENABLED=true and SDK present."""

    def __init__(self, client: Any) -> None:
        self._client = client
        self._capture = resolve_langfuse_capture()

    @classmethod
    def from_env(cls) -> LangfuseSink | None:
        try:
            from langfuse import Langfuse
        except ImportError:
            return None

        public_key = os.getenv("LANGFUSE_PUBLIC_KEY", "").strip()
        secret_key = os.getenv("LANGFUSE_SECRET_KEY", "").strip()
        if not public_key or not secret_key:
            return None

        kwargs = resolve_langfuse_client_kwargs(
            public_key=public_key,
            secret_key=secret_key,
            auto_detect_region=True,
        )
        return cls(Langfuse(**kwargs))

    def record_agent_run(self, log: dict) -> None:
        if not capture_enabled_for_langfuse(self._capture):
            return
        try:
            metadata = {
                "kind": "agent_run",
                "taskId": log.get("taskId"),
                "generationId": log.get("generationId"),
                "promptVersion": log.get("promptVersion"),
                "outputValid": log.get("outputValid"),
                "latencyMs": log.get("latencyMs"),
                "model": log.get("model"),
            }
            metadata.update(_parse_agent_summary_metadata(log.get("inputSummary")))
            self._emit_observation(
                log,
                name=str(log.get("agentName", "agent_run")),
                as_type="span",
                input_val=prepare_payload(log.get("inputSummary"), capture=self._capture),
                metadata=metadata,
            )
        except Exception:
            logger.exception("LangfuseSink.record_agent_run failed")

    def record_tool_run(self, log: dict) -> None:
        if not capture_enabled_for_langfuse(self._capture):
            return
        try:
            metadata = {
                "kind": "tool_run",
                "toolName": log.get("toolName"),
                "taskId": log.get("taskId"),
                "projectId": log.get("projectId"),
                "generationId": log.get("generationId"),
                "latencyMs": log.get("latencyMs"),
                "agentName": log.get("agentName"),
                "slotId": log.get("slotId"),
            }
            extra = log.get("metadata")
            if isinstance(extra, dict):
                for key in (
                    "backend",
                    "acpAgent",
                    "acpTraceDir",
                    "repairAttempt",
                    "eventKind",
                    "lintCached",
                    "outputValid",
                    "sessionUpdateDropped",
                ):
                    if key in extra:
                        metadata[key] = extra[key]
            span_name = str(log.get("toolName", "tool_run"))
            if str(log.get("agentName")) == "material_author" and span_name.startswith("acp_"):
                span_name = f"material_author:{span_name}"
            self._emit_observation(
                log,
                name=span_name,
                as_type="tool",
                input_val=prepare_payload(log.get("input"), capture=self._capture),
                metadata=metadata,
            )
        except Exception:
            logger.exception("LangfuseSink.record_tool_run failed")

    def record_model_call(self, log: dict) -> None:
        if not capture_enabled_for_langfuse(self._capture):
            return
        try:
            call_kind = str(log.get("callKind", "model_call"))
            name = call_kind
            if log.get("agentName"):
                name = f"{log['agentName']}:{call_kind}"
            if log.get("turn") is not None:
                name = f"{name}:turn-{log['turn']}"

            metadata = {
                "kind": "model_call",
                "callKind": call_kind,
                "profile": log.get("profile"),
                "driver": log.get("driver"),
                "taskId": log.get("taskId"),
                "generationId": log.get("generationId"),
                "projectId": log.get("projectId"),
                "agentName": log.get("agentName"),
                "slotId": log.get("slotId"),
                "turn": log.get("turn"),
                "jobId": log.get("jobId"),
                "outputValid": log.get("outputValid"),
                "latencyMs": log.get("latencyMs"),
                "error": log.get("error"),
            }
            input_val = prepare_payload(log.get("input"), capture=self._capture)
            output_val = prepare_payload(log.get("output"), capture=self._capture)
            usage = log.get("tokenUsage")
            usage_details = (
                _normalize_token_usage(usage) if isinstance(usage, dict) else None
            )

            if call_kind in {"video_submit", "video_poll"}:
                self._emit_observation(
                    log,
                    name=name,
                    as_type="span",
                    input_val=input_val,
                    output_val=output_val,
                    metadata=metadata,
                )
            else:
                self._emit_observation(
                    log,
                    name=name,
                    as_type="generation",
                    input_val=input_val,
                    output_val=output_val,
                    metadata=metadata,
                    model=str(log.get("model", "unknown")),
                    usage_details=usage_details,
                )
        except Exception:
            logger.exception("LangfuseSink.record_model_call failed")

    def amend_model_call(self, patch: dict) -> None:
        if not capture_enabled_for_langfuse(self._capture):
            return
        try:
            self._emit_observation(
                patch,
                name="model_call_invalidated",
                as_type="span",
                metadata={
                    "kind": "model_call_amendment",
                    "callId": patch.get("id"),
                    "outputValid": patch.get("outputValid"),
                    "error": patch.get("error"),
                },
            )
        except Exception:
            logger.exception("LangfuseSink.amend_model_call failed")

    def flush(self) -> None:
        try:
            self._client.flush()
        except Exception:
            logger.exception("LangfuseSink.flush failed")

    def _trace_id_for(self, log: dict) -> str:
        task_id = log.get("taskId")
        seed = f"task-{task_id}" if task_id else str(log.get("id", "videomaker"))
        return self._client.create_trace_id(seed=seed)

    def _emit_observation(
        self,
        log: dict,
        *,
        name: str,
        as_type: str,
        input_val: Any = None,
        output_val: Any = None,
        metadata: dict[str, Any] | None = None,
        model: str | None = None,
        usage_details: dict[str, int] | None = None,
    ) -> None:
        from langfuse import propagate_attributes

        task_id = log.get("taskId")
        project_id = log.get("projectId")
        trace_id = self._trace_id_for(log)

        attr_kwargs: dict[str, Any] = {}
        if project_id:
            attr_kwargs["user_id"] = str(project_id)
        if task_id:
            attr_kwargs["session_id"] = str(task_id)

        trace_metadata = {
            "taskId": task_id,
            "projectId": project_id,
            "generationId": log.get("generationId"),
        }

        obs_kwargs: dict[str, Any] = {
            "name": name,
            "as_type": as_type,
            "trace_context": {"trace_id": trace_id},
        }
        if input_val is not None:
            obs_kwargs["input"] = input_val
        if output_val is not None:
            obs_kwargs["output"] = output_val
        if metadata:
            obs_kwargs["metadata"] = metadata
        if model:
            obs_kwargs["model"] = model
        if usage_details:
            obs_kwargs["usage_details"] = usage_details

        with propagate_attributes(metadata=trace_metadata, **attr_kwargs):
            observation = self._client.start_observation(**obs_kwargs)
            observation.end()
