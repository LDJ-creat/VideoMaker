from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any, Callable

from app.gateway.model_gateway import ModelGateway
from app.validation.schema_loader import ValidationErrorItem, validate_contract


class LLMToolConfigError(RuntimeError):
    """Raised when LLM tool configuration is invalid."""


class LLMToolValidationError(RuntimeError):
    """Raised when model output does not pass contract validation."""

    def __init__(
        self,
        message: str,
        *,
        raw_output: str | None,
        validation_errors: list[ValidationErrorItem],
    ) -> None:
        super().__init__(message)
        self.raw_output = raw_output
        self.validation_errors = validation_errors


ModelBackend = Callable[[str, dict[str, Any]], dict[str, Any] | str]


@dataclass
class LLMTool:
    fixture_mode: bool = True
    fixtures: dict[str, dict[str, Any]] | None = None
    backend: ModelBackend | None = None
    gateway: ModelGateway | None = None
    api_key_env: str = "OPENAI_API_KEY"

    def __post_init__(self) -> None:
        self.fixtures = self.fixtures or {}
        self.last_raw_output: str | None = None

    def generate_json(
        self,
        task: str,
        inputs: dict[str, Any],
        schema_name: str | None,
        *,
        profile: str = "text",
    ) -> dict[str, Any]:
        if self.fixture_mode:
            if task not in self.fixtures:
                raise LLMToolConfigError(f"No fixture configured for task '{task}'")
            payload = json.loads(json.dumps(self.fixtures[task], ensure_ascii=False))
            self.last_raw_output = json.dumps(payload, ensure_ascii=False)
            if schema_name is None:
                return payload
            return self._validate_payload(payload=payload, schema_name=schema_name)

        if self.gateway is not None:
            payload = self.gateway.complete_json(
                task,
                inputs,
                schema_name,
                profile=profile,
            )
            self.last_raw_output = json.dumps(payload, ensure_ascii=False)
            if schema_name is None:
                return payload
            return self._validate_payload(payload=payload, schema_name=schema_name)

        if self.backend is not None:
            api_key = os.getenv(self.api_key_env)
            if not api_key:
                raise LLMToolConfigError(
                    f"Missing API key env '{self.api_key_env}' for live LLM mode"
                )
            raw = self.backend(task, inputs)
            if isinstance(raw, str):
                self.last_raw_output = raw
                payload = json.loads(raw)
            else:
                payload = raw
                self.last_raw_output = json.dumps(payload, ensure_ascii=False)
            if schema_name is None:
                return payload
            return self._validate_payload(payload=payload, schema_name=schema_name)

        raise LLMToolConfigError("No ModelGateway configured for live mode")

    def _validate_payload(
        self, *, payload: dict[str, Any], schema_name: str
    ) -> dict[str, Any]:
        validation = validate_contract(schema_name, payload)
        if validation.valid:
            return payload
        raise LLMToolValidationError(
            f"LLM output failed schema validation for '{schema_name}'",
            raw_output=self.last_raw_output,
            validation_errors=validation.errors,
        )


def load_agent_fixtures(fixtures_dir: Path | None = None) -> dict[str, dict[str, Any]]:
    """Load static JSON fixtures for fixture_mode agent tasks.

    CI uses fixture_mode only; outputs are keyed by task name and do not vary
    with runtime inputs until live LLM paths are validated downstream.
    """
    if fixtures_dir is None:
        fixtures_dir = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "agents"
    fixtures: dict[str, dict[str, Any]] = {}
    if not fixtures_dir.is_dir():
        return fixtures
    for path in sorted(fixtures_dir.glob("*.json")):
        fixtures[path.stem] = json.loads(path.read_text(encoding="utf-8"))
    return fixtures


def default_fixture_llm() -> LLMTool:
    return LLMTool(fixture_mode=True, fixtures=load_agent_fixtures())
