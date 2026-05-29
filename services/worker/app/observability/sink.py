from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Protocol, runtime_checkable

from app.runtime.agent_run_store import AgentRunLog, AgentRunStore

logger = logging.getLogger(__name__)


@runtime_checkable
class ObservabilitySink(Protocol):
    def record_agent_run(self, log: dict) -> None: ...

    # Deferred for P1: no worker tool call sites yet; LocalFileSink persists when wired.
    def record_tool_run(self, log: dict) -> None: ...


class LocalFileSink:
    """Persist agent/tool run logs under storage/projects/{projectId}/logs/."""

    def __init__(self, store: AgentRunStore) -> None:
        self._store = store

    def record_agent_run(self, log: dict) -> None:
        project_id = log.get("projectId")
        if not project_id:
            raise ValueError("Agent run log requires projectId for LocalFileSink")

        self._store.record(
            project_id=str(project_id),
            log=AgentRunLog(
                agent_name=str(log["agentName"]),
                prompt_version=str(log["promptVersion"]),
                model=str(log["model"]),
                task=str(log.get("task", "")),
                input_summary=str(log.get("inputSummary", "")),
                output_valid=bool(log["outputValid"]),
                latency_ms=float(log["latencyMs"]),
                task_id=log.get("taskId"),
                generation_id=log.get("generationId"),
                validation_errors=list(log.get("validationErrors", [])),
                token_usage=log.get("tokenUsage"),
                run_id=log.get("id"),
                created_at=log.get("createdAt"),
            ),
        )

    def record_tool_run(self, log: dict) -> None:
        """Persist tool run JSON when a call site is added (P1 interface only)."""
        project_id = log.get("projectId")
        if not project_id:
            return

        tool_dir = (
            self._store.storage_root
            / "projects"
            / str(project_id)
            / "logs"
            / "tool-runs"
        )
        tool_dir.mkdir(parents=True, exist_ok=True)
        run_id = str(log.get("id", "tool-run"))
        (tool_dir / f"{run_id}.json").write_text(
            json.dumps(log, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )


class MultiSink:
    def __init__(self, sinks: list[ObservabilitySink]) -> None:
        self._sinks = list(sinks)

    def record_agent_run(self, log: dict) -> None:
        for sink in self._sinks:
            try:
                sink.record_agent_run(log)
            except Exception:
                logger.exception(
                    "observability sink failed during record_agent_run: %s",
                    type(sink).__name__,
                )

    def record_tool_run(self, log: dict) -> None:
        for sink in self._sinks:
            try:
                sink.record_tool_run(log)
            except Exception:
                logger.exception(
                    "observability sink failed during record_tool_run: %s",
                    type(sink).__name__,
                )


def _langfuse_enabled() -> bool:
    return os.getenv("LANGFUSE_ENABLED", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def build_observability_sink(storage_root: str | Path) -> ObservabilitySink:
    sinks: list[ObservabilitySink] = [LocalFileSink(AgentRunStore(Path(storage_root)))]
    if _langfuse_enabled():
        from app.observability.langfuse_sink import LangfuseSink

        langfuse_sink = LangfuseSink.from_env()
        if langfuse_sink is not None:
            sinks.append(langfuse_sink)
    if len(sinks) == 1:
        return sinks[0]
    return MultiSink(sinks)
