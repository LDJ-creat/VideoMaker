from __future__ import annotations

import atexit
import json
import logging
import os
from pathlib import Path
from typing import Protocol, runtime_checkable

from app.runtime.agent_run_store import AgentRunLog, AgentRunStore
from app.runtime.model_call_store import ModelCallLog, ModelCallStore

logger = logging.getLogger(__name__)

_registered_sinks: list[ObservabilitySink] = []
_atexit_registered = False


@runtime_checkable
class ObservabilitySink(Protocol):
    def record_agent_run(self, log: dict) -> None: ...

    def record_tool_run(self, log: dict) -> None: ...

    def record_model_call(self, log: dict) -> None: ...

    def amend_model_call(self, patch: dict) -> None: ...

    def flush(self) -> None: ...


def register_observability_sink_for_flush(sink: ObservabilitySink) -> None:
    global _atexit_registered
    if sink not in _registered_sinks:
        _registered_sinks.append(sink)
    if not _atexit_registered:
        atexit.register(_flush_all_registered_sinks)
        _atexit_registered = True


def _flush_all_registered_sinks() -> None:
    for sink in list(_registered_sinks):
        try:
            sink.flush()
        except Exception:
            logger.exception("observability atexit flush failed for %s", type(sink).__name__)


class LocalFileSink:
    """Persist agent/model run logs under storage/projects/{projectId}/logs/."""

    def __init__(
        self,
        agent_store: AgentRunStore,
        model_store: ModelCallStore | None = None,
    ) -> None:
        self._store = agent_store
        self._model_store = model_store or ModelCallStore(agent_store.storage_root)

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

    def record_model_call(self, log: dict) -> None:
        from app.observability.capture import capture_enabled_for_local, resolve_observability_capture

        if not capture_enabled_for_local(resolve_observability_capture()):
            return

        project_id = log.get("projectId")
        if not project_id:
            raise ValueError("Model call log requires projectId for LocalFileSink")

        self._model_store.record(
            project_id=str(project_id),
            log=ModelCallLog(
                call_kind=str(log["callKind"]),
                profile=str(log["profile"]),
                model=str(log["model"]),
                driver=str(log["driver"]),
                output_valid=bool(log["outputValid"]),
                latency_ms=float(log["latencyMs"]),
                task_id=log.get("taskId"),
                generation_id=log.get("generationId"),
                slot_id=log.get("slotId"),
                agent_name=log.get("agentName"),
                turn=log.get("turn"),
                job_id=log.get("jobId"),
                input_payload=log.get("input"),
                output_payload=log.get("output"),
                token_usage=log.get("tokenUsage"),
                error=log.get("error"),
                run_id=log.get("id"),
                created_at=log.get("createdAt"),
            ),
        )

    def amend_model_call(self, patch: dict) -> None:
        project_id = patch.get("projectId")
        call_id = patch.get("id")
        if not project_id or not call_id:
            return
        self._model_store.update_output_valid(
            project_id=str(project_id),
            call_id=str(call_id),
            output_valid=bool(patch.get("outputValid", False)),
            error=patch.get("error") if isinstance(patch.get("error"), dict) else None,
        )

    def flush(self) -> None:
        return


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

    def record_model_call(self, log: dict) -> None:
        for sink in self._sinks:
            try:
                sink.record_model_call(log)
            except Exception:
                logger.exception(
                    "observability sink failed during record_model_call: %s",
                    type(sink).__name__,
                )

    def amend_model_call(self, patch: dict) -> None:
        for sink in self._sinks:
            try:
                sink.amend_model_call(patch)
            except Exception:
                logger.exception(
                    "observability sink failed during amend_model_call: %s",
                    type(sink).__name__,
                )

    def flush(self) -> None:
        for sink in self._sinks:
            try:
                sink.flush()
            except Exception:
                logger.exception(
                    "observability sink failed during flush: %s",
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
    root = Path(storage_root)
    agent_store = AgentRunStore(root)
    sinks: list[ObservabilitySink] = [
        LocalFileSink(agent_store, ModelCallStore(root)),
    ]
    if _langfuse_enabled():
        from app.observability.langfuse_sink import LangfuseSink

        langfuse_sink = LangfuseSink.from_env()
        if langfuse_sink is not None:
            sinks.append(langfuse_sink)
        else:
            logger.warning(
                "LANGFUSE_ENABLED is set but Langfuse export is inactive. "
                "Install langfuse in the worker Python used by API subprocesses "
                "(services/api/.venv or services/worker/.venv): "
                "pip install \"langfuse>=4.0,<5\""
            )
    if len(sinks) == 1:
        sink: ObservabilitySink = sinks[0]
    else:
        sink = MultiSink(sinks)
    register_observability_sink_for_flush(sink)
    return sink
