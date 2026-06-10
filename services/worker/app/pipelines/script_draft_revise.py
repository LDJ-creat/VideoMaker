from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from app.agents.runner import AgentRunner
from app.agents.storyboard_writer import run_storyboard_writer
from app.knowledge.context_resolver import resolve_knowledge_context
from app.pipelines.narration_scene_timing import (
    clear_narration_preview,
    load_narration_preview,
    narration_timing_payload,
    unmark_checkpoint_stage,
)
from app.pipelines.script_draft import load_script_draft, save_script_draft
from app.runtime.checkpoint import generation_artifact_root
from app.runtime.task_context import TaskContext
from knowledge.paths import assert_under_storage_root, validate_storage_segment

ScriptReviseScope = Literal["master", "storyboard"]


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def _revision_root(generation_root: Path, revision_id: str, storage_root: Path) -> Path:
    safe_id = validate_storage_segment(revision_id, field="revision_id")
    path = generation_root / "script-nl-revisions" / safe_id
    return assert_under_storage_root(path, storage_root)


def _append_revision_index(generation_root: Path, meta: dict[str, Any]) -> None:
    index_path = generation_root / "script-nl-revisions" / "index.jsonl"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    with index_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(meta, ensure_ascii=False) + "\n")


def _write_revision_artifact(
    generation_root: Path,
    *,
    storage_root: Path,
    revision_id: str,
    meta: dict[str, Any],
    inputs: dict[str, Any],
    raw_output: str | None,
    normalized: dict[str, Any] | None,
    error: dict[str, Any] | None = None,
) -> Path:
    root = _revision_root(generation_root, revision_id, storage_root)
    root.mkdir(parents=True, exist_ok=True)
    (root / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    (root / "inputs.json").write_text(json.dumps(inputs, ensure_ascii=False, indent=2), encoding="utf-8")
    if raw_output is not None:
        raw_path = root / "raw-output.json"
        try:
            parsed = json.loads(raw_output)
            raw_path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")
        except json.JSONDecodeError:
            (root / "raw-output.txt").write_text(raw_output, encoding="utf-8")
    if normalized is not None:
        (root / "normalized.json").write_text(
            json.dumps(normalized, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    if error is not None:
        (root / "error.json").write_text(json.dumps(error, ensure_ascii=False, indent=2), encoding="utf-8")
    _append_revision_index(generation_root, meta)
    return root


def _load_structure(generation_root: Path, structure: dict[str, Any] | None) -> dict[str, Any]:
    if isinstance(structure, dict) and structure:
        return structure
    scaled = _read_json(generation_root / "structure-scaled.json")
    if scaled is not None:
        return scaled
    raise ValueError("structure is required for script draft NL revise")


def _load_duration_target(generation_root: Path, draft: dict[str, Any]) -> dict[str, Any]:
    from_file = _read_json(generation_root / "duration-target.json")
    if isinstance(from_file, dict) and from_file.get("targetSec") is not None:
        return from_file
    target_sec = draft.get("durationTargetSec")
    if target_sec is not None:
        return {"targetSec": float(target_sec)}
    return {"targetSec": 30.0}


def _structure_summary(structure: dict[str, Any]) -> dict[str, Any]:
    slots = structure.get("slots") if isinstance(structure.get("slots"), list) else []
    metadata = structure.get("metadata") if isinstance(structure.get("metadata"), dict) else {}
    return {
        "slotCount": len(slots),
        "durationSec": metadata.get("durationSec"),
        "version": structure.get("version"),
    }


def _load_sample_analysis(
    storage_root: Path,
    project_id: str,
    sample_id: str,
) -> dict[str, Any] | None:
    if not sample_id:
        return None
    analysis_path = (
        storage_root
        / "projects"
        / project_id
        / "samples"
        / sample_id
        / "analysis"
        / "sample-analysis.json"
    )
    if not analysis_path.is_file():
        return None
    payload = json.loads(analysis_path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def _weak_slot_count(gap_report: dict[str, Any]) -> int:
    weak_slots = gap_report.get("weakSlots")
    if isinstance(weak_slots, list):
        return len(weak_slots)
    return 0


def _resolve_knowledge_context_for_revise(
    *,
    storage_root: Path,
    database_path: Path | None,
    project_id: str,
    structure: dict[str, Any],
    gap_report: dict[str, Any],
) -> dict[str, Any]:
    sample_id = str(structure.get("sourceVideoId") or "").strip()
    sample_analysis = (
        _load_sample_analysis(storage_root, project_id, sample_id) if sample_id else None
    )
    return resolve_knowledge_context(
        storage_root=storage_root,
        database_path=database_path,
        project_id=project_id,
        level=1,
        weak_slot_count=_weak_slot_count(gap_report),
        video_structure=structure,
        sample_analysis=sample_analysis,
    )


def revise_script_draft(
    runner: AgentRunner,
    *,
    project_id: str,
    generation_id: str,
    scope: ScriptReviseScope,
    instruction: str,
    context: TaskContext,
    structure: dict[str, Any] | None = None,
    database_path: Path | None = None,
) -> dict[str, Any]:
    instruction_text = str(instruction or "").strip()
    if not instruction_text:
        raise ValueError("instruction must not be empty")

    validate_storage_segment(project_id, field="project_id")
    validate_storage_segment(generation_id, field="generation_id")

    project_root = Path(context.storage_root) / "projects" / project_id
    generation_root = generation_artifact_root(project_root, generation_id)
    if not generation_root.is_dir():
        raise FileNotFoundError(f"Generation artifacts not found: {generation_root}")

    storage_root_path = Path(context.storage_root)

    draft = load_script_draft(generation_root)
    if draft is None:
        raise FileNotFoundError("script-draft.json not found")

    if scope == "master":
        if draft.get("masterNarrationStatus") == "approved":
            raise ValueError("Master narration already approved")
        phase = "revise_master"
    elif scope == "storyboard":
        if draft.get("masterNarrationStatus") != "approved":
            raise ValueError("Master narration must be approved before storyboard revise")
        if draft.get("storyboardStatus") == "approved":
            raise ValueError("Storyboard already approved")
        phase = "revise_storyboard"
    else:
        raise ValueError(f"Invalid scope: {scope}")

    structure_payload = _load_structure(generation_root, structure)
    inventory = _read_json(generation_root / "asset-inventory.json") or {
        "projectId": project_id,
        "assets": [],
    }
    gap_report = _read_json(generation_root / "gap-report.json") or {}
    duration_target = _load_duration_target(generation_root, draft)
    variant = str(draft.get("variant") or "default")
    knowledge_context = _resolve_knowledge_context_for_revise(
        storage_root=storage_root_path,
        database_path=database_path,
        project_id=project_id,
        structure=structure_payload,
        gap_report=gap_report if isinstance(gap_report, dict) else {},
    )

    revision_id = str(uuid.uuid4())
    meta_base = {
        "revisionId": revision_id,
        "generationId": generation_id,
        "projectId": project_id,
        "scope": scope,
        "instruction": instruction_text,
        "phase": phase,
        "taskId": context.task_id,
        "createdAt": _utc_now_iso(),
    }

    llm_inputs: dict[str, Any] = {
        "phase": phase,
        "instruction": instruction_text,
        "structureSummary": _structure_summary(structure_payload),
        "durationTarget": duration_target,
        "variant": variant,
    }
    if knowledge_context.get("primary") is not None:
        llm_inputs["knowledgeContext"] = {
            "level": knowledge_context.get("level"),
            "primaryEntryId": (knowledge_context.get("primary") or {}).get("entryId"),
            "referenceEntryIds": [
                item.get("entryId")
                for item in knowledge_context.get("references") or []
                if isinstance(item, dict) and item.get("entryId")
            ],
        }
    if scope == "master":
        llm_inputs["masterNarration"] = str(draft.get("masterNarration") or "")
        if isinstance(draft.get("visualStyleBible"), dict):
            llm_inputs["visualStyleBible"] = draft["visualStyleBible"]
    else:
        llm_inputs["masterNarration"] = str(draft.get("masterNarration") or "")
        llm_inputs["storyboard"] = list(draft.get("storyboard") or [])
        if isinstance(draft.get("visualStyleBible"), dict):
            llm_inputs["visualStyleBible"] = draft["visualStyleBible"]

    writer_kwargs: dict[str, Any] = {
        "structure": structure_payload,
        "inventory": inventory,
        "gap_report": gap_report,
        "context": context,
        "generation_id": generation_id,
        "variant": variant,
        "phase": phase,
        "duration_target": duration_target,
        "instruction": instruction_text,
        "master_narration": str(draft.get("masterNarration") or ""),
        "knowledge_context": knowledge_context,
    }
    if scope == "storyboard":
        writer_kwargs["current_storyboard"] = [
            dict(scene) for scene in draft.get("storyboard") or [] if isinstance(scene, dict)
        ]
        preview = load_narration_preview(generation_root)
        narration_timing = narration_timing_payload(preview) if preview else None
        if narration_timing is not None:
            writer_kwargs["narration_timing"] = narration_timing
    if isinstance(draft.get("visualStyleBible"), dict):
        writer_kwargs["visual_style_bible"] = dict(draft["visualStyleBible"])

    normalized: dict[str, Any] | None = None
    raw_output: str | None = None
    try:
        writer_output = run_storyboard_writer(runner, **writer_kwargs)
        raw_output = runner.llm.last_raw_output
        summary = str(writer_output.get("summary") or "").strip() or None
        normalized = dict(writer_output)

        merged = dict(draft)
        if scope == "master":
            merged["masterNarration"] = str(writer_output.get("masterNarration") or "")
            if isinstance(writer_output.get("visualStyleBible"), dict):
                merged["visualStyleBible"] = writer_output["visualStyleBible"]
            from app.pipelines.tts_voice_options import normalize_vo_directive, report_vo_directive_warnings

            narration_profile, narration_warnings = normalize_vo_directive(
                writer_output.get("narrationVoProfile")
            )
            report_vo_directive_warnings(narration_warnings, emit_event=context.emit_event)
            if narration_profile:
                merged["narrationVoProfile"] = narration_profile
            else:
                merged.pop("narrationVoProfile", None)
            merged["masterNarrationStatus"] = "draft"
            clear_narration_preview(generation_root)
            unmark_checkpoint_stage(generation_root, "narration_preview")
            merged.pop("narrationPreviewDurationSec", None)
        else:
            merged["storyboard"] = list(writer_output.get("storyboard") or [])
            merged["storyboardStatus"] = "draft"

        saved = save_script_draft(generation_root, merged)
        meta = {**meta_base, "outputValid": True}
        if summary:
            meta["summary"] = summary
        _write_revision_artifact(
            generation_root,
            storage_root=storage_root_path,
            revision_id=revision_id,
            meta=meta,
            inputs=llm_inputs,
            raw_output=raw_output,
            normalized=normalized,
        )
        return {
            "ok": True,
            "draft": saved,
            "summary": summary,
            "revisionId": revision_id,
        }
    except Exception as exc:
        raw_output = runner.llm.last_raw_output
        meta = {**meta_base, "outputValid": False}
        _write_revision_artifact(
            generation_root,
            storage_root=storage_root_path,
            revision_id=revision_id,
            meta=meta,
            inputs=llm_inputs,
            raw_output=raw_output,
            normalized=normalized,
            error={"type": type(exc).__name__, "message": str(exc)},
        )
        raise
