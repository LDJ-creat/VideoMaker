from __future__ import annotations

from dataclasses import dataclass
import json
import os
from typing import Any, Callable

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
    api_key_env: str = "OPENAI_API_KEY"

    def __post_init__(self) -> None:
        self.fixtures = self.fixtures or {}
        self.last_raw_output: str | None = None

    def generate_json(
        self,
        task: str,
        inputs: dict[str, Any],
        schema_name: str,
    ) -> dict[str, Any]:
        if self.fixture_mode:
            if task not in self.fixtures:
                raise LLMToolConfigError(f"No fixture configured for task '{task}'")
            payload = json.loads(json.dumps(self.fixtures[task], ensure_ascii=False))
            self.last_raw_output = json.dumps(payload, ensure_ascii=False)
            return self._validate_payload(payload=payload, schema_name=schema_name)

        api_key = os.getenv(self.api_key_env)
        if not api_key:
            raise LLMToolConfigError(
                f"Missing API key env '{self.api_key_env}' for live LLM mode"
            )
        if self.backend is None:
            raise LLMToolConfigError("No LLM backend configured for live mode")

        raw = self.backend(task, inputs)
        if isinstance(raw, str):
            self.last_raw_output = raw
            payload = json.loads(raw)
        else:
            payload = raw
            self.last_raw_output = json.dumps(payload, ensure_ascii=False)
        return self._validate_payload(payload=payload, schema_name=schema_name)

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

