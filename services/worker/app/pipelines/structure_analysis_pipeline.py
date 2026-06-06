from __future__ import annotations

import json
import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from app.agents.runner import AgentRunner
from app.agents.segment_analyst import run_segment_analyst
from app.agents.segment_proposer import run_segment_proposer
from app.agents.structure_compiler import run_structure_compiler
from app.agents.structure_critic import run_structure_critic
from app.perception.digest_coverage import resolve_segment_vision_policy
from app.agents.failure_debug import (
    format_validation_errors,
    write_structure_agent_failure_debug,
)
from app.agents.structure_inputs import build_structure_analyst_inputs, KeyframeEncodingError
from app.runtime.checkpoint import AnalysisCheckpoint, should_skip_analysis_stage
from app.runtime.task_context import TaskContext
from app.tools.llm_tool import LLMToolConfigError, LLMToolValidationError
from app.validation.schema_loader import validate_contract
from app.validation.structure_coercer import coerce_video_structure
from app.validation.structure_quality import evaluate_structure_quality
from app.validation.structure_validator import StructureValidationError, validate_video_structure


logger = logging.getLogger(__name__)

EmitFn = Callable[..., None]
_MAX_SEGMENT_WORKERS = 4
_MAX_SEGMENT_RETRIES = 1
_MAX_REPAIR_ATTEMPTS = 1


def _proposal_path(analysis_root: Path) -> Path:
    return analysis_root / "segment-proposal.json"


def _segment_analyses_path(analysis_root: Path) -> Path:
    return analysis_root / "segment-analyses.json"


def _persist_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _load_json(path: Path) -> Any | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _validate_structure_payload(
    payload: dict[str, Any],
    *,
    project_id: str,
    source_video_id: str,
    analysis: dict[str, Any],
    reference_shots: list[dict[str, Any]],
) -> dict[str, Any]:
    normalized = coerce_video_structure(
        payload,
        project_id=project_id,
        source_video_id=source_video_id,
        analysis=analysis,
    )
    validation = validate_contract("video-structure", normalized)
    if not validation.valid:
        raise LLMToolValidationError(
            "LLM output failed schema validation for 'video-structure'",
            raw_output=json.dumps(payload, ensure_ascii=False),
            validation_errors=validation.errors,
        )
    return validate_video_structure(
        normalized,
        reference_shots=reference_shots,
        analysis=analysis,
    )


def _run_segment_with_retry(
    runner: AgentRunner,
    *,
    segment: dict[str, Any],
    analysis: dict[str, Any],
    analysis_root: Path,
    context: TaskContext,
) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(_MAX_SEGMENT_RETRIES + 1):
        try:
            return run_segment_analyst(
                runner,
                segment=segment,
                segment_analysis_seed=None,
                analysis=analysis,
                analysis_root=analysis_root,
                context=context,
            )
        except (LLMToolValidationError, LLMToolConfigError, StructureValidationError) as exc:
            last_error = exc
            if attempt >= _MAX_SEGMENT_RETRIES:
                raise
    raise last_error or RuntimeError("segment analysis failed")


def _collect_segment_vision_warnings(
    proposal: dict[str, Any],
    analysis: dict[str, Any],
) -> list[str]:
    warnings: list[str] = []
    for segment in proposal.get("segments") or []:
        if not isinstance(segment, dict):
            continue
        use_vision, _ = resolve_segment_vision_policy(segment, analysis)
        if not use_vision:
            segment_id = str(segment.get("id") or "unknown")
            warnings.append(f"segment_{segment_id}_vision_skipped_digest_coverage")
    return warnings


def _analyze_segments(
    runner: AgentRunner,
    *,
    proposal: dict[str, Any],
    analysis: dict[str, Any],
    analysis_root: Path,
    context: TaskContext,
) -> list[dict[str, Any]]:
    segments = list(proposal.get("segments") or [])
    if not segments:
        return []

    if len(segments) <= 1 or runner.llm.fixture_mode:
        return [
            _run_segment_with_retry(
                runner,
                segment=segment,
                analysis=analysis,
                analysis_root=analysis_root,
                context=context,
            )
            for segment in segments
        ]

    results: list[dict[str, Any] | None] = [None] * len(segments)
    with ThreadPoolExecutor(max_workers=min(_MAX_SEGMENT_WORKERS, len(segments))) as pool:
        future_map = {
            pool.submit(
                _run_segment_with_retry,
                runner,
                segment=segment,
                analysis=analysis,
                analysis_root=analysis_root,
                context=context,
            ): index
            for index, segment in enumerate(segments)
        }
        for future in as_completed(future_map):
            index = future_map[future]
            try:
                results[index] = future.result()
            except Exception as exc:
                segment = segments[index]
                logger.warning(
                    "parallel segment analysis failed for %s, retrying serially: %s",
                    segment.get("id"),
                    exc,
                )
                results[index] = _run_segment_with_retry(
                    runner,
                    segment=segment,
                    analysis=analysis,
                    analysis_root=analysis_root,
                    context=context,
                )
    return [item for item in results if item is not None]


def run_structure_analysis_pipeline(
    runner: AgentRunner,
    *,
    analysis: dict[str, Any],
    context: TaskContext,
    project_id: str,
    source_video_id: str,
    analysis_root: Path | str | None = None,
    progress: int = 92,
    emit: EmitFn | None = None,
    checkpoint: AnalysisCheckpoint | None = None,
    checkpoint_path: Path | None = None,
    resume: bool = False,
) -> dict[str, Any]:
    root = Path(analysis_root) if analysis_root is not None else None
    if root is None:
        raise ValueError("analysis_root is required for structure analysis pipeline")

    packaged = build_structure_analyst_inputs(
        analysis,
        analysis_root=root,
        require_keyframe_files=not runner.llm.fixture_mode,
    )
    reference_shots = list(packaged.get("shots", []))
    checkpoint = checkpoint or AnalysisCheckpoint()
    checkpoint_path = checkpoint_path or (root / "checkpoint.json")

    proposal: dict[str, Any]
    if should_skip_analysis_stage("proposing_segments", checkpoint, root, resume=resume):
        loaded = _load_json(_proposal_path(root))
        proposal = loaded if isinstance(loaded, dict) else {"segments": []}
        if emit is not None:
            emit(
                status="running",
                stage="analyzing_segments",
                progress=87,
                message="(resumed) segment proposal ready",
            )
    else:
        if emit is not None:
            emit(
                status="running",
                stage="analyzing_segments",
                progress=87,
                message="Proposing narrative segments",
            )
        proposal = run_segment_proposer(
            runner,
            analysis=analysis,
            context=context,
            progress=87,
        )
        _persist_json(_proposal_path(root), proposal)
        checkpoint.mark_stage_complete("proposing_segments")
        checkpoint.save(checkpoint_path)

    segment_analyses: list[dict[str, Any]]
    if should_skip_analysis_stage("analyzing_segments", checkpoint, root, resume=resume):
        loaded = _load_json(_segment_analyses_path(root))
        segment_analyses = loaded if isinstance(loaded, list) else []
        if emit is not None:
            emit(
                status="running",
                stage="analyzing_segments",
                progress=88,
                message="(resumed) segment analyses ready",
            )
    else:
        if emit is not None:
            emit(
                status="running",
                stage="analyzing_segments",
                progress=88,
                message="Analyzing narrative segments",
            )
        segment_analyses = _analyze_segments(
            runner,
            proposal=proposal,
            analysis=analysis,
            analysis_root=root,
            context=context,
        )
        _persist_json(_segment_analyses_path(root), segment_analyses)
        checkpoint.mark_stage_complete("analyzing_segments")
        checkpoint.save(checkpoint_path)

    segment_vision_warnings = _collect_segment_vision_warnings(proposal, analysis)

    structure: dict[str, Any] | None = None
    if should_skip_analysis_stage("compiling_structure", checkpoint, root, resume=resume):
        loaded = _load_json(root / "video-structure.json")
        structure = loaded if isinstance(loaded, dict) else None
        if emit is not None:
            emit(
                status="running",
                stage="compiling_structure",
                progress=92,
                message="(resumed) compiled structure ready",
            )
    else:
        if emit is not None:
            emit(
                status="running",
                stage="compiling_structure",
                progress=92,
                message="Compiling VideoStructure v2",
            )

        repair_errors: list[str] | None = None
        for attempt in range(_MAX_REPAIR_ATTEMPTS + 1):
            try:
                payload = run_structure_compiler(
                    runner,
                    analysis=analysis,
                    proposal=proposal,
                    segment_analyses=segment_analyses,
                    project_id=project_id,
                    source_video_id=source_video_id,
                    context=context,
                    progress=progress,
                    validation_errors=repair_errors,
                )
                structure = _validate_structure_payload(
                    payload,
                    project_id=project_id,
                    source_video_id=source_video_id,
                    analysis=analysis,
                    reference_shots=reference_shots,
                )
                break
            except (LLMToolValidationError, StructureValidationError) as exc:
                if attempt >= _MAX_REPAIR_ATTEMPTS:
                    write_structure_agent_failure_debug(
                        analysis_root=root,
                        task_id=context.task_id,
                        exc=exc,
                    )
                    raise
                if isinstance(exc, LLMToolValidationError):
                    repair_errors = format_validation_errors(exc.validation_errors)
                else:
                    repair_errors = exc.errors

        if structure is None:
            raise LLMToolConfigError("Structure compiler produced no output")

        _persist_json(root / "video-structure.json", structure)
        checkpoint.mark_stage_complete("compiling_structure")
        checkpoint.save(checkpoint_path)

    if emit is not None:
        emit(
            status="running",
            stage="critiquing_structure",
            progress=94,
            message="Critiquing structure depth",
        )

    if not should_skip_analysis_stage("critiquing_structure", checkpoint, root, resume=resume):
        critic_warnings: list[str] = []
        try:
            critic = run_structure_critic(runner, structure=structure, context=context, progress=94)
            if not critic.get("approved", True) and isinstance(critic.get("repairs"), dict):
                repaired = dict(structure)
                repaired.update(critic["repairs"])
                structure = _validate_structure_payload(
                    repaired,
                    project_id=project_id,
                    source_video_id=source_video_id,
                    analysis=analysis,
                    reference_shots=reference_shots,
                )
        except StructureValidationError as exc:
            logger.warning("structure_critic repair failed validation: %s", exc)
            critic_warnings.append("critic_repair_failed:validation")
        except Exception as exc:
            logger.warning("structure_critic skipped: %s", exc)
            critic_warnings.append(f"critic_skipped:{type(exc).__name__}")

        quality = evaluate_structure_quality(structure)
        analysis_quality = dict(structure.get("analysisQuality") or {})
        analysis_quality["locale"] = str(
            analysis.get("locale") or analysis_quality.get("locale") or "zh"
        )
        existing_warnings = list(analysis_quality.get("warnings") or [])
        for warning in critic_warnings + list(quality.get("warnings") or []) + segment_vision_warnings:
            if warning not in existing_warnings:
                existing_warnings.append(warning)
        analysis_quality["warnings"] = existing_warnings
        analysis_quality["promoteReady"] = bool(quality.get("promoteReady"))
        structure["analysisQuality"] = analysis_quality
        structure.setdefault("projectId", project_id)
        structure.setdefault("sourceVideoId", source_video_id)
        structure.setdefault("version", "p1-v3")
        _persist_json(root / "video-structure.json", structure)
        checkpoint.mark_stage_complete("critiquing_structure")
        checkpoint.save(checkpoint_path)
    else:
        quality = evaluate_structure_quality(structure)
        analysis_quality = dict(structure.get("analysisQuality") or {})
        if not analysis_quality.get("warnings"):
            analysis_quality["warnings"] = list(quality.get("warnings") or []) + segment_vision_warnings
            analysis_quality["promoteReady"] = bool(quality.get("promoteReady"))
            structure["analysisQuality"] = analysis_quality

    return structure
