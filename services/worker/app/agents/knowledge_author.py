from __future__ import annotations

from typing import Any

from app.agents.runner import AgentRunner
from app.runtime.task_context import TaskContext
from knowledge.index_builder import build_entry_meta, extract_slot_pattern


TASK_KEY = "knowledge_author"
SCHEMA_NAME = "knowledge-skill-output"


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


def run_knowledge_author(
    runner: AgentRunner,
    *,
    structure: dict[str, Any],
    sample_analysis: dict[str, Any] | None,
    context: TaskContext,
    progress: int = 94,
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
        analysis_quality = (structure.get("analysisQuality") or {})
        if analysis_quality.get("warnings"):
            inputs["analysisQuality"] = analysis_quality
    output = runner.run(
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
    return output
