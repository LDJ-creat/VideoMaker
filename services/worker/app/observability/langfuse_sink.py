from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


class LangfuseSink:
    """Optional Langfuse export. Disabled unless LANGFUSE_ENABLED=true and SDK present."""

    def __init__(self, client: Any) -> None:
        self._client = client

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
        try:
            trace = self._client.trace(
                id=str(log.get("id")),
                name=str(log.get("agentName", "agent_run")),
                metadata={
                    "taskId": log.get("taskId"),
                    "generationId": log.get("generationId"),
                    "promptVersion": log.get("promptVersion"),
                    "outputValid": log.get("outputValid"),
                },
            )
            trace.generation(
                name=str(log.get("task", log.get("agentName", "agent_run"))),
                model=str(log.get("model", "unknown")),
                input=log.get("inputSummary"),
                metadata={"latencyMs": log.get("latencyMs")},
            )
        except Exception:
            logger.exception("LangfuseSink.record_agent_run failed")

    def record_tool_run(self, log: dict) -> None:
        try:
            self._client.trace(
                id=str(log.get("id")),
                name=str(log.get("toolName", "tool_run")),
                metadata=log,
            )
        except Exception:
            logger.exception("LangfuseSink.record_tool_run failed")
