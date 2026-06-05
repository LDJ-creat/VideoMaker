from __future__ import annotations

from pathlib import Path
from typing import Any

from app.agents.runner import AgentRunner
from app.agents.structure_inputs import build_structure_analyst_inputs
from app.runtime.task_context import TaskContext
from app.tools.llm_tool import LLMToolValidationError
from app.validation.schema_loader import validate_contract
from app.validation.structure_coercer import _normalize_segment_role


TASK_KEY = "segment_proposer"
SCHEMA_NAME = "segment-proposal"


def _coerce_segment_proposal(payload: dict[str, Any]) -> dict[str, Any]:
    segments: list[dict[str, Any]] = []
    for index, segment in enumerate(list(payload.get("segments") or [])):
        if not isinstance(segment, dict):
            continue
        coerced = dict(segment)
        coerced["role"] = _normalize_segment_role(str(segment.get("role") or "hook"))
        coerced["id"] = str(segment.get("id") or f"seg-{index + 1}")
        segments.append(coerced)
    return {"segments": segments}


def _validate_segment_proposal(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = _coerce_segment_proposal(payload)
    validation = validate_contract(SCHEMA_NAME, normalized)
    if not validation.valid:
        raise LLMToolValidationError(
            f"LLM output failed schema validation for '{SCHEMA_NAME}'",
            raw_output=None,
            validation_errors=validation.errors,
        )
    return normalized


def run_segment_proposer(
    runner: AgentRunner,
    *,
    analysis: dict[str, Any],
    context: TaskContext,
    progress: int = 90,
) -> dict[str, Any]:
    packaged = build_structure_analyst_inputs(analysis, require_keyframe_files=False)
    inputs = {
        "metadata": packaged.get("metadata"),
        "transcript": packaged.get("transcript"),
        "shots": packaged.get("shots"),
        "rhythmFacts": packaged.get("rhythmFacts"),
        "audioProfile": packaged.get("audioProfile"),
        "keyframeBatchDigests": packaged.get("keyframeBatchDigests"),
        "locale": packaged.get("locale", "zh"),
    }
    return runner.run(
        "segment_proposer",
        task=TASK_KEY,
        schema_name=None,
        inputs=inputs,
        context=context,
        progress=progress,
        post_validate=_validate_segment_proposal,
    )


def segment_keyframes(
    segment: dict[str, Any],
    keyframes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    start = float(segment.get("startSec", 0.0))
    end = float(segment.get("endSec", start))
    selected: list[dict[str, Any]] = []
    for frame in keyframes:
        time_sec = float(frame.get("timeSec", -1.0))
        if start - 0.05 <= time_sec <= end + 0.05:
            selected.append(frame)
    return selected
