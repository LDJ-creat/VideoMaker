from __future__ import annotations

from typing import Any

from app.agents.runner import AgentRunner
from app.gateway.providers.base import GatewayError
from app.runtime.task_context import TaskContext
from app.tools.llm_tool import LLMToolValidationError
from knowledge.index_builder import build_entry_meta, extract_slot_pattern


TASK_KEY = "knowledge_author"
SCHEMA_NAME = "knowledge-skill-output"
_MAX_JSON_REPAIR_ATTEMPTS = 1

_JSON_REPAIR_HINT = (
    "Previous output was invalid or truncated JSON. Return ONE compact JSON object with "
    "exactly keys frontmatter and markdown. Keep frontmatter strings short "
    "(rhetoricalPattern <= 60 chars, summary <= 120). Use tempo enum slow|medium|fast|mixed. "
    "Escape newlines in markdown as \\n. Finish the markdown field — do not stop after frontmatter."
)


def _merge_frontmatter(
    payload: dict[str, Any],
    *,
    structure: dict[str, Any],
    sample_analysis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    frontmatter = dict(payload.get("frontmatter") or {})
    rhythm = structure.get("rhythm") if isinstance(structure.get("rhythm"), dict) else {}
    metadata = structure.get("metadata") if isinstance(structure.get("metadata"), dict) else {}
    defaults = build_entry_meta(
        structure,
        title=str(frontmatter.get("title") or "结构经验"),
        category=str(frontmatter.get("category") or "通用短视频"),
        style=str(frontmatter.get("style") or "标准结构"),
        summary=str(frontmatter.get("summary") or "可复用的短视频结构经验"),
        hook_type=frontmatter.get("hookType"),
        sample_analysis=sample_analysis,
    )
    for key, value in defaults.items():
        if value is not None and not frontmatter.get(key):
            frontmatter[key] = value
    if not frontmatter.get("slotPattern"):
        frontmatter["slotPattern"] = extract_slot_pattern(structure)
    if not frontmatter.get("tempo") and rhythm.get("tempo"):
        frontmatter["tempo"] = rhythm.get("tempo")
    payload = dict(payload)
    payload["frontmatter"] = frontmatter
    return payload


def _build_inputs(
    *,
    structure: dict[str, Any],
    sample_analysis: dict[str, Any] | None,
    json_repair_hint: str | None,
) -> dict[str, Any]:
    inputs: dict[str, Any] = {"videoStructure": structure}
    if sample_analysis is not None:
        inputs["sampleAnalysis"] = {
            "metadata": sample_analysis.get("metadata"),
            "warnings": sample_analysis.get("warnings"),
            "audioProfile": sample_analysis.get("audioProfile"),
            "onScreenTextFacts": sample_analysis.get("onScreenTextFacts"),
            "keyframeBatchDigests": sample_analysis.get("keyframeBatchDigests"),
        }
        analysis_quality = structure.get("analysisQuality") or {}
        if analysis_quality.get("warnings"):
            inputs["analysisQuality"] = analysis_quality
    if json_repair_hint:
        inputs["jsonRepairHint"] = json_repair_hint
    return inputs


def run_knowledge_author(
    runner: AgentRunner,
    *,
    structure: dict[str, Any],
    sample_analysis: dict[str, Any] | None,
    context: TaskContext,
    progress: int = 94,
) -> dict[str, Any]:
    json_repair_hint: str | None = None
    last_exc: Exception | None = None

    for attempt in range(_MAX_JSON_REPAIR_ATTEMPTS + 1):
        inputs = _build_inputs(
            structure=structure,
            sample_analysis=sample_analysis,
            json_repair_hint=json_repair_hint,
        )
        try:
            return runner.run(
                "knowledge_author",
                task=TASK_KEY,
                schema_name=SCHEMA_NAME,
                inputs=inputs,
                context=context,
                progress=progress,
                post_validate=lambda payload: _merge_frontmatter(
                    payload,
                    structure=structure,
                    sample_analysis=sample_analysis,
                ),
            )
        except LLMToolValidationError as exc:
            last_exc = exc
            if attempt >= _MAX_JSON_REPAIR_ATTEMPTS:
                raise
            json_repair_hint = _JSON_REPAIR_HINT
        except GatewayError as exc:
            last_exc = exc
            if exc.code != "invalid_json" or attempt >= _MAX_JSON_REPAIR_ATTEMPTS:
                raise
            json_repair_hint = _JSON_REPAIR_HINT

    assert last_exc is not None
    raise last_exc
