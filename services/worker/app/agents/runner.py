from __future__ import annotations

from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass, field
import json
import logging
import time
import uuid
from typing import Any, Iterator

from app.agents.failure_debug import format_validation_errors
from app.agents.prompt_loader import PromptLoader
from app.observability.token_usage import latest_token_usage_from_llm
from app.observability.gateway_context import agent_observability_scope, resolve_profile_model
from app.observability.model_call_recorder import invalidate_last_model_call
from app.observability.sink import ObservabilitySink
from app.runtime.agent_run_store import AgentRunLog
from app.runtime.task_context import TaskContext
from app.tools.llm_tool import LLMTool, LLMToolConfigError, LLMToolValidationError

logger = logging.getLogger(__name__)


@dataclass
class AgentRunner:
    llm: LLMTool
    prompt_loader: PromptLoader
    observability_sink: ObservabilitySink
    model_name: str = "fixture"
    last_agent_run_id: str | None = field(default=None, init=False, repr=False)

    def _resolve_model_name(self, profile: str) -> str:
        if self.llm.fixture_mode:
            return "fixture"
        gateway = self.llm.gateway
        if gateway is None:
            return self.model_name
        return resolve_profile_model(gateway, profile)

    @contextmanager
    def _agent_observability_scope(
        self,
        agent_name: str,
        *,
        profile: str,
    ) -> Iterator[None]:
        gateway = self.llm.gateway
        with agent_observability_scope(gateway, agent_name):
            yield

    def run(
        self,
        agent_name: str,
        *,
        task: str,
        schema_name: str | None,
        inputs: dict[str, Any],
        context: TaskContext,
        progress: int = 50,
        generation_id: str | None = None,
        post_validate: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        profile: str = "text",
    ) -> dict[str, Any]:
        prompt_version = self.prompt_loader.version(agent_name)
        system = self.prompt_loader.load(agent_name)
        merged_inputs = {"systemPrompt": system, "inputs": inputs}
        input_summary = json.dumps(
            {"agent": agent_name, "keys": sorted(inputs.keys())},
            ensure_ascii=False,
        )[:500]

        context.emit_event(
            stage="running_agent",
            progress=progress,
            message=f"Running {agent_name}",
        )

        started = time.perf_counter()
        output: dict[str, Any] | None = None
        valid = True
        errors: list[str] = []
        model_name = self._resolve_model_name(profile)
        with self._agent_observability_scope(agent_name, profile=profile):
            try:
                output = self.llm.generate_json(
                    task,
                    merged_inputs,
                    schema_name,
                    profile=profile,
                )
                if post_validate is not None:
                    output = post_validate(output)
            except LLMToolValidationError as exc:
                valid = False
                errors = format_validation_errors(exc.validation_errors)
                if not self.llm.fixture_mode and self.llm.gateway is not None:
                    invalidate_last_model_call(
                        self.llm.gateway,
                        validation_errors=errors,
                    )
                raise
            except LLMToolConfigError as exc:
                valid = False
                errors = [str(exc)]
                if not self.llm.fixture_mode and self.llm.gateway is not None:
                    invalidate_last_model_call(
                        self.llm.gateway,
                        validation_errors=errors,
                    )
                raise
            except ValueError as exc:
                valid = False
                errors = [str(exc)]
                if not self.llm.fixture_mode and self.llm.gateway is not None:
                    invalidate_last_model_call(
                        self.llm.gateway,
                        validation_errors=errors,
                    )
                raise
            finally:
                latency_ms = (time.perf_counter() - started) * 1000
                run_id = str(uuid.uuid4())
                payload = AgentRunLog(
                    agent_name=agent_name,
                    prompt_version=prompt_version,
                    model=model_name,
                    task=task,
                    input_summary=input_summary,
                    output_valid=valid,
                    latency_ms=latency_ms,
                    task_id=context.task_id,
                    generation_id=generation_id,
                    validation_errors=errors,
                    token_usage=latest_token_usage_from_llm(self.llm),
                    run_id=run_id,
                ).to_payload()
                payload["projectId"] = context.project_id
                self.last_agent_run_id = run_id
                try:
                    self.observability_sink.record_agent_run(payload)
                except ValueError as exc:
                    if "Invalid AgentRunLog payload" not in str(exc):
                        raise
                    logger.warning("agent-run log skipped: %s", exc)

        assert output is not None
        return output
