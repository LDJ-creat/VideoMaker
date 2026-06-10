from __future__ import annotations

import json
from pathlib import Path

from app.agents.failure_debug import (
    format_validation_errors,
    tool_error_from_agent_failure,
    write_structure_agent_failure_debug,
)
from app.tools.llm_tool import LLMToolValidationError
from app.validation.schema_loader import ValidationErrorItem
from app.validation.structure_validator import StructureValidationError


def test_format_validation_errors_includes_path_and_validator() -> None:
    errors = format_validation_errors(
        [
            ValidationErrorItem(
                path="$.slots[0].role",
                message="'role' is a required property",
                validator="required",
            )
        ]
    )
    assert errors == ["$.slots[0].role: 'role' is a required property (required)"]


def test_write_structure_agent_failure_debug_persists_raw_output(tmp_path: Path) -> None:
    exc = LLMToolValidationError(
        "LLM output failed schema validation for 'video-structure'",
        raw_output='{"id":"partial"}',
        validation_errors=[
            ValidationErrorItem(path="$.projectId", message="missing", validator="required")
        ],
    )

    failure_path = write_structure_agent_failure_debug(
        analysis_root=tmp_path,
        task_id="task-1",
        exc=exc,
    )

    summary = json.loads(failure_path.read_text(encoding="utf-8"))
    assert summary["errorType"] == "LLMToolValidationError"
    assert summary["rawOutputPath"] == "structure-llm-raw-output.json"
    assert summary["validationErrors"][0]["path"] == "$.projectId"

    raw = json.loads((tmp_path / "structure-llm-raw-output.json").read_text(encoding="utf-8"))
    assert raw["id"] == "partial"


def test_tool_error_from_agent_failure_uses_llm_validation_code() -> None:
    exc = StructureValidationError(["evidence missing segment refs"])
    payload = tool_error_from_agent_failure(exc)
    assert payload["code"] == "LLMValidationError"
    assert payload["retryable"] is True
    assert payload["details"]["errorType"] == "StructureValidationError"


def test_tool_error_from_agent_failure_marks_invalid_json_retryable() -> None:
    from app.gateway.providers.base import GatewayError

    exc = GatewayError(code="invalid_json", message="bad json", retryable=False)
    payload = tool_error_from_agent_failure(exc)
    assert payload["code"] == "invalid_json"
    assert payload["retryable"] is True
    assert payload["details"]["errorType"] == "GatewayError"
