from __future__ import annotations

import copy
import json
import os
from datetime import datetime, timezone
from typing import Any

from app.agents.runner import AgentRunner
from app.runtime.task_context import TaskContext
from app.tools.llm_tool import LLMToolConfigError, LLMToolValidationError
from app.validation.schema_loader import validate_contract
from app.validation.structure_coercer import coerce_video_structure
from app.validation.structure_validator import StructureValidationError, validate_video_structure


TASK_KEY = "structure_synthesizer"
STRUCTURE_SCHEMA = "video-structure"
PROVENANCE_SCHEMA = "structure-provenance"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _fixture_mode_enabled() -> bool:
    return os.getenv("VIDEOMAKER_FIXTURE_MODE", "true").lower() in ("1", "true", "yes")


def _summarize_structure(structure: dict[str, Any]) -> dict[str, Any]:
    narrative = structure.get("narrative") or {}
    rhythm = structure.get("rhythm") or {}
    packaging = structure.get("packaging") or {}
    slots = structure.get("slots") or []
    return {
        "id": structure.get("id"),
        "sourceVideoId": structure.get("sourceVideoId"),
        "summary": narrative.get("summary"),
        "segmentCount": len(narrative.get("segments") or []),
        "tempo": rhythm.get("tempo"),
        "slotCount": len(slots),
        "visualDensity": packaging.get("visualDensity"),
        "slots": [
            {
                "id": slot.get("id"),
                "role": slot.get("role"),
                "visualIntent": slot.get("visualIntent"),
                "scriptIntent": slot.get("scriptIntent"),
            }
            for slot in slots[:12]
        ],
    }


def _build_fallback_provenance(
    *,
    project_id: str,
    generation_run_id: str,
    primary_sample_id: str,
    reference_sample_ids: list[str],
    structure: dict[str, Any],
    fallback: bool = False,
) -> dict[str, Any]:
    slot_attribution = []
    for slot in structure.get("slots") or []:
        slot_attribution.append(
            {
                "slotId": str(slot.get("id", "")),
                "sourceSampleId": primary_sample_id,
                "sourceSlotId": str(slot.get("id", "")),
                "rationale": "primary_structure_fallback" if fallback else "primary_structure",
            }
        )
    return {
        "id": f"provenance-{generation_run_id}",
        "projectId": project_id,
        "generationRunId": generation_run_id,
        "primarySampleId": primary_sample_id,
        "referenceSampleIds": reference_sample_ids,
        "slotAttribution": slot_attribution,
        "fallback": fallback,
        "createdAt": _now_iso(),
    }


def _validate_provenance(payload: dict[str, Any]) -> dict[str, Any]:
    validation = validate_contract(PROVENANCE_SCHEMA, payload)
    if validation.valid:
        return payload
    raise LLMToolValidationError(
        f"LLM output failed schema validation for '{PROVENANCE_SCHEMA}'",
        raw_output=json.dumps(payload, ensure_ascii=False),
        validation_errors=validation.errors,
    )


def run_structure_synthesizer(
    runner: AgentRunner,
    *,
    context: TaskContext,
    project_id: str,
    generation_run_id: str,
    primary_sample_id: str,
    primary_structure: dict[str, Any],
    reference_structures: list[dict[str, Any]],
    reference_sample_ids: list[str],
    user_brief: dict[str, Any],
    knowledge_context: dict[str, Any] | None = None,
    progress: int = 6,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not reference_structures or _fixture_mode_enabled() or runner.llm.fixture_mode:
        synthesized = copy.deepcopy(primary_structure)
        synthesized["id"] = f"synthesized-{generation_run_id}"
        synthesized["projectId"] = project_id
        synthesized["sourceVideoId"] = primary_sample_id
        provenance = _build_fallback_provenance(
            project_id=project_id,
            generation_run_id=generation_run_id,
            primary_sample_id=primary_sample_id,
            reference_sample_ids=reference_sample_ids,
            structure=synthesized,
            fallback=bool(reference_structures) and (_fixture_mode_enabled() or runner.llm.fixture_mode),
        )
        return synthesized, provenance

    agent_inputs = {
        "projectId": project_id,
        "generationRunId": generation_run_id,
        "primarySampleId": primary_sample_id,
        "referenceSampleIds": reference_sample_ids,
        "primaryStructure": _summarize_structure(primary_structure),
        "referenceStructures": [_summarize_structure(item) for item in reference_structures],
        "userBrief": user_brief,
        "knowledgeContext": knowledge_context,
    }

    try:
        payload = runner.run(
            "structure_synthesizer",
            task=TASK_KEY,
            schema_name=None,
            inputs=agent_inputs,
            context=context,
            profile="text",
        )
    except (LLMToolConfigError, LLMToolValidationError, StructureValidationError):
        synthesized = copy.deepcopy(primary_structure)
        synthesized["id"] = f"synthesized-{generation_run_id}"
        synthesized["projectId"] = project_id
        synthesized["sourceVideoId"] = primary_sample_id
        provenance = _build_fallback_provenance(
            project_id=project_id,
            generation_run_id=generation_run_id,
            primary_sample_id=primary_sample_id,
            reference_sample_ids=reference_sample_ids,
            structure=synthesized,
            fallback=True,
        )
        return synthesized, provenance

    structure_raw = payload.get("structure") if isinstance(payload, dict) else None
    provenance_raw = payload.get("provenance") if isinstance(payload, dict) else None
    if not isinstance(structure_raw, dict):
        raise LLMToolValidationError(
            "structure_synthesizer output missing structure object",
            raw_output=json.dumps(payload, ensure_ascii=False),
            validation_errors=["missing structure"],
        )

    try:
        structure = coerce_video_structure(
            structure_raw,
            project_id=project_id,
            source_video_id=primary_sample_id,
            analysis=None,
        )
        validation = validate_contract(STRUCTURE_SCHEMA, structure)
        if not validation.valid:
            raise LLMToolValidationError(
                f"structure synthesis failed schema validation for '{STRUCTURE_SCHEMA}'",
                raw_output=json.dumps(structure_raw, ensure_ascii=False),
                validation_errors=validation.errors,
            )
        structure = validate_video_structure(structure, reference_shots=[])
        structure["id"] = f"synthesized-{generation_run_id}"
    except (LLMToolValidationError, StructureValidationError):
        synthesized = copy.deepcopy(primary_structure)
        synthesized["id"] = f"synthesized-{generation_run_id}"
        synthesized["projectId"] = project_id
        synthesized["sourceVideoId"] = primary_sample_id
        provenance = _build_fallback_provenance(
            project_id=project_id,
            generation_run_id=generation_run_id,
            primary_sample_id=primary_sample_id,
            reference_sample_ids=reference_sample_ids,
            structure=synthesized,
            fallback=True,
        )
        return synthesized, provenance

    if isinstance(provenance_raw, dict):
        provenance_raw.setdefault("id", f"provenance-{generation_run_id}")
        provenance_raw.setdefault("projectId", project_id)
        provenance_raw.setdefault("generationRunId", generation_run_id)
        provenance_raw.setdefault("primarySampleId", primary_sample_id)
        provenance_raw.setdefault("referenceSampleIds", reference_sample_ids)
        provenance_raw.setdefault("createdAt", _now_iso())
        try:
            provenance = _validate_provenance(provenance_raw)
        except LLMToolValidationError:
            provenance = _build_fallback_provenance(
                project_id=project_id,
                generation_run_id=generation_run_id,
                primary_sample_id=primary_sample_id,
                reference_sample_ids=reference_sample_ids,
                structure=structure,
                fallback=False,
            )
    else:
        provenance = _build_fallback_provenance(
            project_id=project_id,
            generation_run_id=generation_run_id,
            primary_sample_id=primary_sample_id,
            reference_sample_ids=reference_sample_ids,
            structure=structure,
            fallback=False,
        )

    context.emit_event(
        stage="synthesizing_structure",
        progress=progress,
        message="Structure synthesis completed",
    )
    return structure, provenance
