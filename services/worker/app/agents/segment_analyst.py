from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from app.agents.runner import AgentRunner
from app.agents.segment_proposer import segment_keyframes
from app.agents.structure_inputs import _encode_keyframes
from app.gateway.model_gateway import ModelGateway
from app.perception.digest_coverage import resolve_segment_vision_policy
from app.runtime.task_context import TaskContext
from app.tools.llm_tool import LLMTool, LLMToolConfigError, LLMToolValidationError
from app.validation.schema_loader import validate_contract


TASK_KEY = "segment_analyst"
SCHEMA_NAME = "segment-analysis"
_MAX_LIVE_RETRIES = 1
_DENSITY_ALIASES = {
    "低": "low",
    "中": "medium",
    "高": "high",
    "low": "low",
    "medium": "medium",
    "high": "high",
}
_EVIDENCE_PREFIX = re.compile(
    r"^(asr|ocr|keyframe|audio|shot_detection|llm)\s*:\s*(.+)$",
    re.IGNORECASE,
)
_TIME_RANGE_SUFFIX = re.compile(
    r"\((\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*s\)\s*$",
    re.IGNORECASE,
)


def _unwrap_segment_payload(payload: Any) -> dict[str, Any]:
    current = payload
    if isinstance(current, list) and current:
        current = current[0]
    if not isinstance(current, dict):
        raise LLMToolValidationError(
            f"LLM output failed schema validation for '{SCHEMA_NAME}'",
            raw_output=json.dumps(payload, ensure_ascii=False),
            validation_errors=[],
        )
    for _ in range(4):
        validation = validate_contract(SCHEMA_NAME, current)
        if validation.valid:
            return current
        wrapped: dict[str, Any] | None = None
        for key in (SCHEMA_NAME, SCHEMA_NAME.replace("-", "_")):
            candidate = current.get(key)
            if isinstance(candidate, dict):
                wrapped = candidate
                break
        if wrapped is None and len(current) == 1:
            only_value = next(iter(current.values()))
            if isinstance(only_value, dict):
                wrapped = only_value
        if wrapped is None:
            break
        current = wrapped
    return current


_VALID_EVIDENCE_SOURCES = frozenset(
    {"asr", "ocr", "keyframe", "shot_detection", "audio", "llm"}
)


def _normalize_evidence_source(source: Any) -> str:
    raw = str(source or "llm").strip().lower()
    if raw in _VALID_EVIDENCE_SOURCES:
        return raw
    if "transcript" in raw or raw.startswith("asr"):
        return "asr"
    if "onscreen" in raw or "on_screen" in raw or raw.startswith("ocr"):
        return "ocr"
    if "keyframe" in raw or "batchdigest" in raw.replace("_", "") or "frame" in raw:
        return "keyframe"
    if "shot" in raw:
        return "shot_detection"
    if "audio" in raw:
        return "audio"
    return "llm"


_TIME_RANGE_OBJECT = re.compile(
    r"^\(?(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*s?\)?$",
    re.IGNORECASE,
)


def _coerce_time_range(value: Any) -> dict[str, float] | None:
    if isinstance(value, dict):
        start = value.get("startSec")
        end = value.get("endSec")
        if start is not None and end is not None:
            return {"startSec": float(start), "endSec": float(end)}
        return None
    if not isinstance(value, str):
        return None
    text = value.strip()
    match = _TIME_RANGE_OBJECT.match(text)
    if not match:
        return None
    return {"startSec": float(match.group(1)), "endSec": float(match.group(2))}


def _coerce_local_evidence(
    items: list[Any],
    *,
    segment_id: str,
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        if isinstance(item, dict):
            evidence = dict(item)
            evidence["source"] = _normalize_evidence_source(evidence.get("source"))
            evidence.setdefault("targetId", segment_id)
            evidence.setdefault("confidence", 0.7)
            if not str(evidence.get("summary") or "").strip():
                evidence["summary"] = str(evidence.get("excerpt") or evidence.get("source") or "segment evidence")
            coerced_range = _coerce_time_range(evidence.get("timeRange"))
            if coerced_range is not None:
                evidence["timeRange"] = coerced_range
            elif "timeRange" in evidence:
                evidence.pop("timeRange", None)
            normalized.append(evidence)
            continue
        if not isinstance(item, str):
            continue
        text = item.strip()
        source = "llm"
        summary = text
        match = _EVIDENCE_PREFIX.match(text)
        if match:
            source = _normalize_evidence_source(match.group(1))
            summary = match.group(2).strip()
        else:
            source = "llm"
        time_range = _coerce_time_range(summary)
        if time_range is None:
            range_match = _TIME_RANGE_SUFFIX.search(summary)
            if range_match:
                time_range = {
                    "startSec": float(range_match.group(1)),
                    "endSec": float(range_match.group(2)),
                }
                summary = _TIME_RANGE_SUFFIX.sub("", summary).strip().strip("'\"")
        evidence_item: dict[str, Any] = {
            "targetId": segment_id,
            "source": source,
            "summary": summary or text,
            "confidence": 0.7,
        }
        if time_range is not None:
            evidence_item["timeRange"] = time_range
        if source == "asr" and summary:
            evidence_item["excerpt"] = summary.strip("'\"")
        normalized.append(evidence_item)
    return normalized


def _as_mapping(value: Any, *, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    return dict(default or {})


def _coerce_segment_analysis(payload: Any, *, segment_id: str) -> dict[str, Any]:
    coerced = dict(_unwrap_segment_payload(payload))
    coerced["segmentId"] = str(coerced.get("segmentId") or segment_id)
    coerced["transcriptExcerpt"] = str(coerced.get("transcriptExcerpt") or "").strip()
    coerced["emotionTone"] = str(coerced.get("emotionTone") or "中性").strip()
    coerced["rhetoricalDevices"] = [
        str(item).strip()
        for item in (coerced.get("rhetoricalDevices") or [])
        if str(item).strip()
    ] or ["陈述"]

    raw_vo_style = coerced.get("voStyle")
    if isinstance(raw_vo_style, str) and raw_vo_style.strip():
        vo_style = {"pace": raw_vo_style.strip(), "energy": "中等", "persona": "讲述者"}
    else:
        vo_style = _as_mapping(raw_vo_style)
    coerced["voStyle"] = {
        "pace": str(vo_style.get("pace") or "适中"),
        "energy": str(vo_style.get("energy") or "中等"),
        "persona": str(vo_style.get("persona") or "讲述者"),
    }

    raw_visual_spec = coerced.get("visualSpec")
    if isinstance(raw_visual_spec, str) and raw_visual_spec.strip():
        visual_spec = {"framing": raw_visual_spec.strip()}
    else:
        visual_spec = _as_mapping(raw_visual_spec)
    density_raw = str(visual_spec.get("density") or "medium")
    visual_spec["density"] = _DENSITY_ALIASES.get(density_raw.lower(), density_raw)
    if visual_spec["density"] not in {"low", "medium", "high"}:
        visual_spec["density"] = "medium"
    on_screen = visual_spec.get("onScreenText")
    if not isinstance(on_screen, list):
        on_screen = []
    visual_spec["onScreenText"] = [str(item) for item in on_screen if str(item).strip()]
    coerced["visualSpec"] = {
        "framing": str(visual_spec.get("framing") or "中景"),
        "subject": str(visual_spec.get("subject") or "画面主体"),
        "cameraMove": str(visual_spec.get("cameraMove") or "静态"),
        "onScreenText": visual_spec["onScreenText"],
        "colorMood": str(visual_spec.get("colorMood") or "自然"),
        "density": visual_spec["density"],
    }

    ocr_facts: list[dict[str, Any]] = []
    for item in coerced.get("onScreenTextFacts") or []:
        if not isinstance(item, dict):
            continue
        fact = dict(item)
        fact.setdefault("confidence", 0.75)
        ocr_facts.append(fact)
    coerced["onScreenTextFacts"] = ocr_facts
    coerced["localEvidence"] = _coerce_local_evidence(
        list(coerced.get("localEvidence") or []),
        segment_id=coerced["segmentId"],
    )
    return coerced


def _validate_segment_payload(payload: Any, *, segment_id: str) -> dict[str, Any]:
    normalized = _coerce_segment_analysis(payload, segment_id=segment_id)
    validation = validate_contract(SCHEMA_NAME, normalized)
    if not validation.valid:
        raise LLMToolValidationError(
            f"LLM output failed schema validation for '{SCHEMA_NAME}'",
            raw_output=json.dumps(payload, ensure_ascii=False),
            validation_errors=validation.errors,
        )
    return normalized


def run_segment_analyst(
    runner: AgentRunner,
    *,
    segment: dict[str, Any],
    segment_analysis_seed: dict[str, Any] | None,
    analysis: dict[str, Any],
    analysis_root: Path,
    context: TaskContext,
    progress: int = 91,
) -> dict[str, Any]:
    keyframes = segment_keyframes(segment, list(analysis.get("keyframes") or []))
    use_vision, max_keyframes = resolve_segment_vision_policy(segment, analysis)
    encoded = (
        _encode_keyframes(
            keyframes,
            analysis_root=analysis_root,
            max_keyframes=max_keyframes,
        )
        if use_vision
        else []
    )
    transcript = analysis.get("transcript", [])
    if isinstance(transcript, dict):
        transcript_segments = list(transcript.get("segments", []))
    else:
        transcript_segments = list(transcript)

    start_sec = float(segment.get("startSec", 0.0))
    end_sec = float(segment.get("endSec", start_sec))
    overlapping_transcript = [
        item
        for item in transcript_segments
        if isinstance(item, dict)
        and float(item.get("endSec", 0.0)) >= start_sec
        and float(item.get("startSec", 0.0)) <= end_sec
    ]

    inputs: dict[str, Any] = {
        "segment": segment,
        "transcriptSegments": overlapping_transcript,
        "audioProfile": analysis.get("audioProfile"),
        "keyframeBatchDigests": analysis.get("keyframeBatchDigests"),
        "onScreenTextFacts": analysis.get("onScreenTextFacts"),
        "locale": analysis.get("locale", "zh"),
        "visionPolicy": "vision" if use_vision else "text_digest",
    }
    if segment_analysis_seed is not None:
        inputs["seed"] = segment_analysis_seed

    segment_id = str(segment.get("id") or "")
    last_error: Exception | None = None
    for attempt in range(_MAX_LIVE_RETRIES + 1):
        attempt_inputs = dict(inputs)
        if attempt > 0 and last_error is not None:
            attempt_inputs["validationErrors"] = [str(last_error)]

        try:
            if runner.llm.fixture_mode:
                raw_payload = runner.run(
                    "segment_analyst",
                    task=TASK_KEY,
                    schema_name=None,
                    inputs=attempt_inputs,
                    context=context,
                    progress=progress,
                    profile="vision" if encoded else "text",
                    post_validate=lambda payload: _validate_segment_payload(
                        payload,
                        segment_id=segment_id,
                    ),
                )
            else:
                gateway = runner.llm.gateway
                if gateway is None:
                    raise LLMToolConfigError("No ModelGateway configured for segment analyst")
                system_prompt = runner.prompt_loader.load("segment_analyst")
                text_payload = {"systemPrompt": system_prompt, "inputs": attempt_inputs}
                messages = ModelGateway.build_structure_messages(
                    system_prompt=system_prompt,
                    text_payload=text_payload,
                    keyframes=encoded if encoded else None,
                )
                raw_payload = gateway.complete_json_messages(
                    messages,
                    profile="vision" if encoded else "text",
                )
                raw_payload = LLMTool._unwrap_schema_payload(raw_payload, SCHEMA_NAME)
                raw_payload = _validate_segment_payload(raw_payload, segment_id=segment_id)

            payload = dict(raw_payload)
            payload.setdefault("segmentId", segment_id)
            return payload
        except (LLMToolValidationError, LLMToolConfigError) as exc:
            last_error = exc
            if attempt >= _MAX_LIVE_RETRIES:
                raise

    raise AssertionError("segment analyst retry loop exited without result")
