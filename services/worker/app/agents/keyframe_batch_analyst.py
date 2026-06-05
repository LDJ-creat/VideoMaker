from __future__ import annotations

import json
import os
from typing import Any
from app.agents.runner import AgentRunner
from app.agents.structure_inputs import _encode_keyframes, _pick_best_keyframes_per_shot
from app.gateway.model_gateway import ModelGateway
from app.runtime.task_context import TaskContext
from app.validation.schema_loader import validate_contract
from app.tools.llm_tool import LLMToolConfigError, LLMToolValidationError


TASK_KEY = "keyframe_batch_analyst"
SCHEMA_NAME = "keyframe-batch-output"


def _batch_size() -> int:
    raw = os.environ.get("VIDEOMAKER_VISION_BATCH_SIZE", "8").strip()
    try:
        return max(1, min(12, int(raw)))
    except ValueError:
        return 8


def _max_calls() -> int:
    raw = os.environ.get("VIDEOMAKER_VISION_BATCH_MAX_CALLS", "6").strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return 6


def chunk_keyframes(
    keyframes: list[dict[str, Any]],
    *,
    batch_size: int | None = None,
    max_calls: int | None = None,
) -> list[list[dict[str, Any]]]:
    size = batch_size or _batch_size()
    ordered = _pick_best_keyframes_per_shot(keyframes)
    if not ordered:
        return []
    batches: list[list[dict[str, Any]]] = []
    for index in range(0, len(ordered), size):
        batches.append(ordered[index : index + size])
    call_limit = max_calls if max_calls is not None else _max_calls()
    return batches[:call_limit]


def vision_batch_frame_cap(max_calls: int | None = None) -> int:
    return _batch_size() * (max_calls if max_calls is not None else _max_calls())


def run_keyframe_batch_analyst(
    runner: AgentRunner,
    *,
    batch_index: int,
    batch_keyframes: list[dict[str, Any]],
    analysis: dict[str, Any],
    analysis_root,
    context: TaskContext,
    progress: int = 86,
) -> dict[str, Any]:
    encoded = _encode_keyframes(
        batch_keyframes,
        analysis_root=analysis_root,
        max_keyframes=len(batch_keyframes),
    )
    transcript = analysis.get("transcript", [])
    if isinstance(transcript, dict):
        transcript_segments = list(transcript.get("segments", []))
    else:
        transcript_segments = list(transcript)

    start_sec = float(batch_keyframes[0].get("timeSec", 0.0)) if batch_keyframes else 0.0
    end_sec = float(batch_keyframes[-1].get("timeSec", start_sec)) if batch_keyframes else start_sec

    inputs = {
        "batchIndex": batch_index,
        "startSec": start_sec,
        "endSec": end_sec,
        "transcriptSegments": transcript_segments,
        "frames": [
            {
                "shotId": frame.get("shotId"),
                "timeSec": frame.get("timeSec"),
                "path": frame.get("path"),
            }
            for frame in batch_keyframes
        ],
    }

    if runner.llm.fixture_mode:
        payload = runner.run(
            "keyframe_batch_analyst",
            task=TASK_KEY,
            schema_name=SCHEMA_NAME,
            inputs=inputs,
            context=context,
            progress=progress,
            profile="vision" if encoded else "text",
        )
    else:
        gateway = runner.llm.gateway
        if gateway is None:
            raise LLMToolConfigError("No ModelGateway configured for keyframe batch analyst")
        system_prompt = runner.prompt_loader.load("keyframe_batch_analyst")
        text_payload = {"systemPrompt": system_prompt, "inputs": inputs}
        messages = ModelGateway.build_structure_messages(
            system_prompt=system_prompt,
            text_payload=text_payload,
            keyframes=encoded if encoded else None,
        )
        payload = gateway.complete_json_messages(
            messages,
            profile="vision" if encoded else "text",
        )
        validation = validate_contract(SCHEMA_NAME, payload)
        if not validation.valid:
            raise LLMToolValidationError(
                f"LLM output failed schema validation for '{SCHEMA_NAME}'",
                raw_output=json.dumps(payload, ensure_ascii=False),
                validation_errors=validation.errors,
            )

    return {
        "batchIndex": batch_index,
        "startSec": start_sec,
        "endSec": end_sec,
        "frames": inputs["frames"],
        "visualFacts": str(payload.get("visualFacts") or ""),
        "onScreenTextFacts": list(payload.get("onScreenTextFacts") or []),
    }
