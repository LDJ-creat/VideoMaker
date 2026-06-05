from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from app.agents.failure_debug import (
    format_validation_errors,
    write_structure_agent_failure_debug,
)
from app.agents.runner import AgentRunner
from app.agents.structure_inputs import build_structure_analyst_inputs, compute_rhythm_facts
from app.gateway.model_gateway import ModelGateway
from app.runtime.agent_run_store import AgentRunLog
from app.runtime.task_context import TaskContext
from app.tools.llm_tool import LLMToolConfigError, LLMToolValidationError
from app.validation.schema_loader import validate_contract
from app.validation.structure_coercer import coerce_video_structure
from app.validation.structure_validator import StructureValidationError, validate_video_structure


TASK_KEY = "video_structure_analyst"
SCHEMA_NAME = "video-structure"
_MAX_REPAIR_ATTEMPTS = 1


def _transcript_summary(transcript: Any) -> dict[str, Any]:
    if isinstance(transcript, dict):
        segments = list(transcript.get("segments") or [])
        return {
            "language": transcript.get("language"),
            "segmentCount": len(segments),
            "preview": [
                {
                    "startSec": item.get("startSec"),
                    "endSec": item.get("endSec"),
                    "text": str(item.get("text") or "")[:80],
                }
                for item in segments[:8]
                if isinstance(item, dict)
            ],
        }
    if isinstance(transcript, list):
        return {"segmentCount": len(transcript)}
    return {"segmentCount": 0}


def _slim_audio_profile(audio_profile: Any) -> dict[str, Any] | None:
    if not isinstance(audio_profile, dict):
        return None
    return {
        "hasVoiceover": audio_profile.get("hasVoiceover"),
        "hasBgm": audio_profile.get("hasBgm"),
        "onsetTimes": list(audio_profile.get("onsetTimes") or [])[:48],
        "avgSpeechRate": audio_profile.get("avgSpeechRate"),
    }


def build_direct_video_text_payload(analysis: dict[str, Any]) -> dict[str, Any]:
    metadata = analysis.get("metadata", {})
    shots = list(analysis.get("shots") or [])
    payload: dict[str, Any] = {
        "metadata": metadata,
        "transcriptSummary": _transcript_summary(analysis.get("transcript")),
        "rhythmFacts": compute_rhythm_facts(
            shots,
            duration_sec=metadata.get("durationSec") if isinstance(metadata, dict) else None,
        ),
        "locale": str(analysis.get("locale") or "zh"),
    }
    audio_profile = _slim_audio_profile(analysis.get("audioProfile"))
    if audio_profile is not None:
        payload["audioProfile"] = audio_profile
    return payload


def _assert_video_understanding_limits(
    video_path: Path,
    *,
    duration_sec: float | None,
) -> None:
    max_mb = float(os.getenv("VIDEOMAKER_VIDEO_UNDERSTANDING_MAX_MB", "50"))
    max_sec = float(os.getenv("VIDEOMAKER_VIDEO_UNDERSTANDING_MAX_SEC", "300"))
    size_mb = video_path.stat().st_size / (1024 * 1024)
    if size_mb > max_mb:
        raise ValueError(
            f"Sample video {size_mb:.1f}MB exceeds direct multimodal limit {max_mb}MB"
        )
    if duration_sec is not None and float(duration_sec) > max_sec:
        raise ValueError(
            f"Sample duration {duration_sec}s exceeds direct multimodal limit {max_sec}s"
        )


def _validate_schema(
    payload: dict[str, Any],
    *,
    project_id: str,
    source_video_id: str,
    analysis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized = coerce_video_structure(
        payload,
        project_id=project_id,
        source_video_id=source_video_id,
        analysis=analysis,
    )
    validation = validate_contract(SCHEMA_NAME, normalized)
    if validation.valid:
        return normalized
    raise LLMToolValidationError(
        f"LLM output failed schema validation for '{SCHEMA_NAME}'",
        raw_output=json.dumps(payload, ensure_ascii=False),
        validation_errors=validation.errors,
    )


def _post_validate(
    structure: dict[str, Any],
    *,
    reference_shots: list[dict[str, Any]],
    analysis: dict[str, Any] | None,
) -> dict[str, Any]:
    return validate_video_structure(
        structure,
        reference_shots=reference_shots,
        analysis=analysis,
    )


def _run_live(
    runner: AgentRunner,
    *,
    system_prompt: str,
    agent_inputs: dict[str, Any],
    text_payload: dict[str, Any],
    video_path: Path,
    reference_shots: list[dict[str, Any]],
    analysis: dict[str, Any],
    context: TaskContext,
    progress: int,
) -> dict[str, Any]:
    gateway = runner.llm.gateway
    if gateway is None:
        raise LLMToolConfigError("No ModelGateway configured for live mode")

    _assert_video_understanding_limits(
        video_path,
        duration_sec=(analysis.get("metadata") or {}).get("durationSec")
        if isinstance(analysis.get("metadata"), dict)
        else None,
    )

    context.emit_event(
        stage="running_agent",
        progress=progress,
        message="Running video_structure_analyst",
    )
    started = time.perf_counter()
    text_message = {"systemPrompt": system_prompt, "inputs": agent_inputs}
    messages = ModelGateway.build_video_structure_messages(
        system_prompt=system_prompt,
        text_payload=text_payload,
        text_message=text_message,
        video_path=video_path,
    )
    output: dict[str, Any] | None = None
    valid = True
    errors: list[str] = []
    try:
        payload = gateway.complete_json_messages(messages, profile="video_understanding")
        project_id = str(agent_inputs.get("projectId", ""))
        source_video_id = str(agent_inputs.get("sourceVideoId", ""))
        output = _validate_schema(
            payload,
            project_id=project_id,
            source_video_id=source_video_id,
            analysis=analysis,
        )
        output = _post_validate(
            output,
            reference_shots=reference_shots,
            analysis=analysis,
        )
    except LLMToolValidationError as exc:
        valid = False
        errors = format_validation_errors(exc.validation_errors)
        raise
    except StructureValidationError as exc:
        valid = False
        errors = list(exc.errors)
        raise
    except LLMToolConfigError as exc:
        valid = False
        errors = [str(exc)]
        raise
    finally:
        latency_ms = (time.perf_counter() - started) * 1000
        payload = AgentRunLog(
            agent_name="video_structure_analyst",
            prompt_version=runner.prompt_loader.version("video_structure_analyst"),
            model=runner.model_name,
            task=TASK_KEY,
            input_summary=json.dumps(
                {"agent": "video_structure_analyst", "videoPath": str(video_path.name)},
                ensure_ascii=False,
            )[:500],
            output_valid=valid,
            latency_ms=latency_ms,
            task_id=context.task_id,
            validation_errors=errors,
        ).to_payload()
        payload["projectId"] = context.project_id
        runner.observability_sink.record_agent_run(payload)
    assert output is not None
    return output


def run_video_structure_analyst(
    runner: AgentRunner,
    *,
    analysis: dict[str, Any],
    video_path: Path | str,
    context: TaskContext,
    project_id: str,
    source_video_id: str,
    analysis_root: Path | str | None = None,
    progress: int = 90,
) -> dict[str, Any]:
    root = Path(analysis_root) if analysis_root is not None else None
    resolved_video = Path(video_path)
    if not resolved_video.is_file():
        raise FileNotFoundError(f"Sample video not found: {resolved_video}")

    packaged = build_structure_analyst_inputs(analysis, require_keyframe_files=False)
    reference_shots = list(packaged.get("shots") or [])
    text_payload = build_direct_video_text_payload(analysis)
    agent_inputs: dict[str, Any] = {
        "projectId": project_id,
        "sourceVideoId": source_video_id,
        "locale": packaged.get("locale", "zh"),
        "analysis": text_payload,
    }

    repair_errors: list[str] | None = None
    for attempt in range(_MAX_REPAIR_ATTEMPTS + 1):
        attempt_inputs = dict(agent_inputs)
        if repair_errors:
            attempt_inputs["validationErrors"] = repair_errors
        try:
            if runner.llm.fixture_mode:
                structure = runner.run(
                    "video_structure_analyst",
                    task=TASK_KEY,
                    schema_name=SCHEMA_NAME,
                    inputs=attempt_inputs,
                    context=context,
                    progress=progress,
                    post_validate=lambda output: _post_validate(
                        output,
                        reference_shots=reference_shots,
                        analysis=analysis,
                    ),
                )
            else:
                system_prompt = runner.prompt_loader.load("video_structure_analyst")
                structure = _run_live(
                    runner,
                    system_prompt=system_prompt,
                    agent_inputs=attempt_inputs,
                    text_payload=text_payload,
                    video_path=resolved_video,
                    reference_shots=reference_shots,
                    analysis=analysis,
                    context=context,
                    progress=progress,
                )
            structure.setdefault("projectId", project_id)
            structure.setdefault("sourceVideoId", source_video_id)
            structure.setdefault("version", "p1-v2")
            return structure
        except LLMToolValidationError as exc:
            if attempt >= _MAX_REPAIR_ATTEMPTS:
                if root is not None:
                    write_structure_agent_failure_debug(
                        analysis_root=root,
                        task_id=context.task_id,
                        exc=exc,
                    )
                raise
            repair_errors = format_validation_errors(exc.validation_errors)
        except StructureValidationError as exc:
            if attempt >= _MAX_REPAIR_ATTEMPTS:
                if root is not None:
                    write_structure_agent_failure_debug(
                        analysis_root=root,
                        task_id=context.task_id,
                        exc=exc,
                    )
                raise
            repair_errors = exc.errors

    raise AssertionError("video structure analyst repair loop exited without result")
