from __future__ import annotations

import logging
import os
from typing import Any

from app.observability.capture import (
    capture_enabled_for_langfuse,
    prepare_payload,
    resolve_langfuse_capture,
)

logger = logging.getLogger(__name__)


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

        host = os.getenv("LANGFUSE_HOST", "").strip() or None
        kwargs: dict[str, Any] = {
            "public_key": public_key,
            "secret_key": secret_key,
        }
        if host:
            kwargs["host"] = host
        return cls(Langfuse(**kwargs))

    def record_agent_run(self, log: dict) -> None:
        if not capture_enabled_for_langfuse(self._capture):
            return
        try:
            trace = self._task_trace(log)
            trace.span(
                id=str(log.get("id")),
                name=str(log.get("agentName", "agent_run")),
                input=prepare_payload(log.get("inputSummary"), capture=self._capture),
                metadata={
                    "kind": "agent_run",
                    "taskId": log.get("taskId"),
                    "generationId": log.get("generationId"),
                    "promptVersion": log.get("promptVersion"),
                    "outputValid": log.get("outputValid"),
                    "latencyMs": log.get("latencyMs"),
                    "model": log.get("model"),
                },
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
            }
            self._task_trace(log).span(
                id=str(log.get("id")),
                name=str(log.get("toolName", "tool_run")),
                metadata=metadata,
            )
        except Exception:
            logger.exception("LangfuseSink.record_tool_run failed")

    def record_model_call(self, log: dict) -> None:
        if not capture_enabled_for_langfuse(self._capture):
            return
        try:
            trace = self._task_trace(log)
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
            usage = log.get("tokenUsage")
            generation_kwargs: dict[str, Any] = {
                "id": str(log.get("id")),
                "name": name,
                "model": str(log.get("model", "unknown")),
                "input": prepare_payload(log.get("input"), capture=self._capture),
                "output": prepare_payload(log.get("output"), capture=self._capture),
                "metadata": metadata,
            }
            if isinstance(usage, dict):
                generation_kwargs["usage"] = usage

            if call_kind in {"video_submit", "video_poll"}:
                trace.span(
                    id=str(log.get("id")),
                    name=name,
                    input=generation_kwargs.get("input"),
                    output=generation_kwargs.get("output"),
                    metadata=metadata,
                )
            else:
                trace.generation(**generation_kwargs)
        except Exception:
            logger.exception("LangfuseSink.record_model_call failed")

    def amend_model_call(self, patch: dict) -> None:
        if not capture_enabled_for_langfuse(self._capture):
            return
        try:
            trace = self._task_trace(patch)
            trace.span(
                id=f"{patch.get('id')}-invalidated",
                name="model_call_invalidated",
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

    def _task_trace(self, log: dict) -> Any:
        task_id = log.get("taskId")
        project_id = log.get("projectId")
        trace_id = f"task-{task_id}" if task_id else str(log.get("id"))
        kwargs: dict[str, Any] = {
            "id": trace_id,
            "name": "videomaker_task",
        }
        if task_id:
            kwargs["session_id"] = str(task_id)
        if project_id:
            kwargs["user_id"] = str(project_id)
        metadata = {
            "taskId": task_id,
            "projectId": project_id,
            "generationId": log.get("generationId"),
        }
        kwargs["metadata"] = metadata
        return self._client.trace(**kwargs)
