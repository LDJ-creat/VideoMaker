from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import json
import time
from typing import Any

from app.agents.failure_debug import format_validation_errors
from app.observability.sink import ObservabilitySink
from app.runtime.agent_run_store import AgentRunLog
from app.runtime.task_context import TaskContext
from app.tools.llm_tool import LLMTool, LLMToolConfigError, LLMToolValidationError


@dataclass
class AgentRunner:
    llm: LLMTool
    prompt_loader: PromptLoader
    observability_sink: ObservabilitySink
    model_name: str = "fixture"

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
            raise
        except LLMToolConfigError as exc:
            valid = False
            errors = [str(exc)]
            raise
        except ValueError as exc:
            valid = False
            errors = [str(exc)]
            raise
        finally:
            latency_ms = (time.perf_counter() - started) * 1000
            payload = AgentRunLog(
                agent_name=agent_name,
                prompt_version=prompt_version,
                model=self.model_name,
                task=task,
                input_summary=input_summary,
                output_valid=valid,
                latency_ms=latency_ms,
                task_id=context.task_id,
                generation_id=generation_id,
                validation_errors=errors,
            ).to_payload()
            payload["projectId"] = context.project_id
            self.observability_sink.record_agent_run(payload)

        assert output is not None
        return output
