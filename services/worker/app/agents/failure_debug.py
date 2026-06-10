from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.gateway.providers.base import GatewayError
from app.tools.llm_tool import LLMToolConfigError, LLMToolValidationError
from app.validation.schema_loader import ValidationErrorItem
from app.validation.structure_validator import StructureValidationError

logger = logging.getLogger(__name__)

_RAW_OUTPUT_JSON = "structure-llm-raw-output.json"
_RAW_OUTPUT_TEXT = "structure-llm-raw-output.txt"
_FAILURE_FILENAME = "structure-agent-failure.json"


def format_validation_errors(errors: list[ValidationErrorItem]) -> list[str]:
    return [
        f"{item.path}: {item.message} ({item.validator})"
        for item in errors
    ]


def agent_failure_details(exc: Exception) -> dict[str, Any]:
    if isinstance(exc, LLMToolValidationError):
        return {
            "errorType": "LLMToolValidationError",
            "validationErrors": [
                {
                    "path": item.path,
                    "message": item.message,
                    "validator": item.validator,
                }
                for item in exc.validation_errors
            ],
        }
    if isinstance(exc, StructureValidationError):
        return {
            "errorType": "StructureValidationError",
            "validationErrors": list(exc.errors),
        }
    if isinstance(exc, LLMToolConfigError):
        return {"errorType": "LLMToolConfigError", "message": str(exc)}
    if isinstance(exc, GatewayError):
        return {"errorType": "GatewayError", "code": exc.code, "message": exc.message}
    return {"errorType": type(exc).__name__, "message": str(exc)}


def tool_error_from_agent_failure(exc: Exception) -> dict[str, Any]:
    code = "agent_failed"
    retryable = True
    if isinstance(exc, (LLMToolValidationError, StructureValidationError)):
        code = "LLMValidationError"
    elif isinstance(exc, GatewayError):
        code = exc.code
        retryable = exc.retryable or exc.code == "invalid_json"
    return {
        "code": code,
        "message": str(exc),
        "retryable": retryable,
        "details": agent_failure_details(exc),
    }


def write_structure_agent_failure_debug(
    *,
    analysis_root: Path,
    task_id: str | None,
    exc: Exception,
    raw_output: str | None = None,
) -> Path:
    """Persist schema/semantic validation failures for sample structure extraction."""
    root = Path(analysis_root)
    root.mkdir(parents=True, exist_ok=True)

    if isinstance(exc, LLMToolValidationError):
        raw_output = raw_output or exc.raw_output

    raw_output_path: str | None = None
    if raw_output:
        try:
            parsed = json.loads(raw_output)
            raw_file = root / _RAW_OUTPUT_JSON
            raw_file.write_text(
                json.dumps(parsed, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except json.JSONDecodeError:
            raw_file = root / _RAW_OUTPUT_TEXT
            raw_file.write_text(raw_output, encoding="utf-8")
        raw_output_path = raw_file.name

    summary: dict[str, Any] = {
        "agentName": "structure_analyst",
        "taskId": task_id,
        "createdAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "message": str(exc),
        **agent_failure_details(exc),
    }
    if raw_output_path:
        summary["rawOutputPath"] = raw_output_path

    failure_path = root / _FAILURE_FILENAME
    failure_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    logger.warning(
        "structure_analyst failed task_id=%s failure_file=%s validation_errors=%s",
        task_id,
        failure_path,
        summary.get("validationErrors"),
    )
    return failure_path
