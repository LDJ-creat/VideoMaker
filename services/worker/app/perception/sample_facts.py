from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.agents.keyframe_batch_analyst import (
    chunk_keyframes,
    run_keyframe_batch_analyst,
    vision_batch_frame_cap,
)
from app.agents.runner import AgentRunner
from app.agents.structure_inputs import _pick_best_keyframes_per_shot, compute_rhythm_facts
from app.perception.analysis_depth import (
    default_vision_batch_max_calls,
    resolve_analysis_depth,
)
from app.perception.keyframe_sampler import select_keyframes_for_llm
from app.perception.visual_facts_progress import (
    is_visual_facts_stage_complete,
    load_batch_digest,
    load_existing_digests,
    load_visual_facts_progress,
    save_batch_digest,
    save_visual_facts_progress,
    sync_progress_from_disk,
)
from app.runtime.task_context import TaskContext
from app.tools.llm_tool import LLMToolConfigError, LLMToolValidationError

_SAMPLE_ANALYSIS_PATH_KEYS = frozenset(
    {
        "metadataPath",
        "audioPath",
        "transcriptPath",
        "shotsPath",
        "keyframesPath",
        "sourcePath",
    }
)


def slim_audio_profile(full: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(full, dict):
        return None
    slim: dict[str, Any] = {
        "hasVoiceover": full.get("hasVoiceover"),
        "hasBgm": full.get("hasBgm"),
        "onsetTimes": list(full.get("onsetTimes") or []),
        "metrics": full.get("metrics"),
        "avgSpeechRate": full.get("avgSpeechRate"),
    }
    return {key: value for key, value in slim.items() if value is not None}


def batch_digest_index_entry(digest: dict[str, Any]) -> dict[str, Any]:
    batch_index = int(digest.get("batchIndex", 0))
    return {
        "batchIndex": batch_index,
        "startSec": digest.get("startSec"),
        "endSec": digest.get("endSec"),
        "digestRef": f"batch-digests/batch-{batch_index}.json",
    }


def batch_digest_index_entries(batch_digests: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        batch_digest_index_entry(item)
        for item in batch_digests
        if isinstance(item, dict)
    ]


def aggregate_on_screen_text_facts(
    batch_digests: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for digest in batch_digests:
        for fact in digest.get("onScreenTextFacts") or []:
            if not isinstance(fact, dict):
                continue
            key = (
                fact.get("timeSec"),
                fact.get("keyframePath"),
                fact.get("text"),
            )
            if key in seen:
                continue
            seen.add(key)
            merged.append(fact)
    return merged


def merge_visual_facts_into_sample_analysis(
    sample_analysis: dict[str, Any],
    *,
    batch_digests: list[dict[str, Any]],
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    merged = dict(sample_analysis)
    for path_key in _SAMPLE_ANALYSIS_PATH_KEYS:
        merged.pop(path_key, None)
    merged["keyframeBatchDigests"] = batch_digest_index_entries(batch_digests)
    merged["onScreenTextFacts"] = aggregate_on_screen_text_facts(batch_digests)
    if warnings:
        existing = list(merged.get("warnings") or [])
        for warning in warnings:
            if warning not in existing:
                existing.append(warning)
        merged["warnings"] = existing
    return merged


@dataclass
class VisualFactsExtractionResult:
    batch_digests: list[dict[str, Any]]
    warnings: list[str] = field(default_factory=list)
    stage_complete: bool = False
    stopped_early: bool = False


def _batch_failure_warning(batch_index: int, exc: Exception) -> str:
    detail = getattr(exc, "code", None) or str(exc)
    detail = str(detail).replace("\n", " ").strip()[:120]
    return f"vision_batch_{batch_index}_failed:{type(exc).__name__}:{detail}"


def _append_vision_batch_truncation_warning(
    warnings: list[str],
    *,
    llm_keyframes: list[dict[str, Any]],
    max_calls: int,
) -> None:
    ordered = _pick_best_keyframes_per_shot(llm_keyframes)
    frame_cap = vision_batch_frame_cap(max_calls)
    if len(ordered) > frame_cap:
        warning = f"vision_batch_truncated:{len(ordered)}->{frame_cap}"
        if warning not in warnings:
            warnings.append(warning)


def _persist_partial_visual_facts(
    *,
    analysis_root: Path,
    sample_analysis: dict[str, Any],
    total: int,
    warnings: list[str],
) -> list[dict[str, Any]]:
    digests = load_existing_digests(analysis_root, total)
    merged_analysis = merge_visual_facts_into_sample_analysis(
        sample_analysis,
        batch_digests=digests,
        warnings=warnings,
    )
    persist_sample_analysis(analysis_root, merged_analysis)
    return digests


def _record_batch_failure(
    analysis_root: Path,
    *,
    batch_index: int,
    total: int,
    exc: Exception,
    warnings: list[str],
) -> None:
    warnings.append(_batch_failure_warning(batch_index, exc))
    progress = sync_progress_from_disk(analysis_root, total_batches=total)
    failed = {int(item) for item in progress.get("failedIndices") or [] if str(item).isdigit()}
    failed.add(batch_index)
    progress["failedIndices"] = sorted(failed)
    progress["lastError"] = str(exc)
    save_visual_facts_progress(analysis_root, progress)


def _prepare_llm_keyframes(sample_analysis: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str], str]:
    keyframes = list(sample_analysis.get("keyframes") or [])
    shots = list(sample_analysis.get("shots") or [])
    metadata = sample_analysis.get("metadata") or {}
    duration_sec = float(metadata.get("durationSec") or 0.0)
    rhythm_facts = compute_rhythm_facts(shots, duration_sec=duration_sec)
    audio_profile = sample_analysis.get("audioProfile")
    depth = resolve_analysis_depth(
        audio_profile=audio_profile if isinstance(audio_profile, dict) else None,
        rhythm_facts=rhythm_facts,
    )
    selected, warnings = select_keyframes_for_llm(
        keyframes,
        shots,
        duration_sec=duration_sec,
        analysis_depth=depth,
    )
    return selected, warnings, depth


def run_visual_facts_extraction(
    runner: AgentRunner,
    *,
    sample_analysis: dict[str, Any],
    analysis_root: Path,
    context: TaskContext,
    progress_start: int = 84,
) -> VisualFactsExtractionResult:
    llm_keyframes, sampler_warnings, depth = _prepare_llm_keyframes(sample_analysis)
    sample_analysis = dict(sample_analysis)
    sample_analysis["analysisDepth"] = depth
    warnings = list(sampler_warnings)

    if not llm_keyframes:
        persist_sample_analysis(analysis_root, sample_analysis)
        return VisualFactsExtractionResult(batch_digests=[], warnings=warnings, stage_complete=True)

    max_calls = default_vision_batch_max_calls(depth)
    batches = chunk_keyframes(llm_keyframes, max_calls=max_calls)
    _append_vision_batch_truncation_warning(
        warnings,
        llm_keyframes=llm_keyframes,
        max_calls=max_calls,
    )
    if not batches:
        persist_sample_analysis(analysis_root, sample_analysis)
        return VisualFactsExtractionResult(batch_digests=[], warnings=warnings, stage_complete=True)

    new_total = len(batches)
    existing_progress = load_visual_facts_progress(analysis_root)
    stored_total = int(existing_progress.get("totalBatches") or 0) if existing_progress else 0
    if stored_total > 0 and stored_total != new_total:
        warning = f"visual_facts_batch_plan_changed:{stored_total}->{new_total}"
        if warning not in warnings:
            warnings.append(warning)
    total = new_total

    progress = sync_progress_from_disk(analysis_root, total_batches=total)
    progress["totalBatches"] = total
    save_visual_facts_progress(analysis_root, progress)

    digests = load_existing_digests(analysis_root, total)

    for index, batch in enumerate(batches):
        if load_batch_digest(analysis_root, index) is not None:
            continue

        batch_progress = progress_start + int((index + 1) / max(total, 1) * 6)
        try:
            digest = run_keyframe_batch_analyst(
                runner,
                batch_index=index,
                batch_keyframes=batch,
                analysis=sample_analysis,
                analysis_root=analysis_root,
                context=context,
                progress=batch_progress,
            )
        except Exception as exc:
            _record_batch_failure(
                analysis_root,
                batch_index=index,
                total=total,
                exc=exc,
                warnings=warnings,
            )
            digests = _persist_partial_visual_facts(
                analysis_root=analysis_root,
                sample_analysis=sample_analysis,
                total=total,
                warnings=warnings,
            )
            stage_complete = is_visual_facts_stage_complete(analysis_root, total_batches=total)
            return VisualFactsExtractionResult(
                batch_digests=digests,
                warnings=warnings,
                stage_complete=stage_complete,
                stopped_early=True,
            )

        save_batch_digest(analysis_root, index, digest)
        progress = sync_progress_from_disk(analysis_root, total_batches=total)
        progress["failedIndices"] = [
            item for item in progress.get("failedIndices") or [] if int(item) != index
        ]
        progress["lastError"] = None
        save_visual_facts_progress(analysis_root, progress)

        digests = _persist_partial_visual_facts(
            analysis_root=analysis_root,
            sample_analysis=sample_analysis,
            total=total,
            warnings=warnings,
        )

    stage_complete = is_visual_facts_stage_complete(analysis_root, total_batches=total)
    return VisualFactsExtractionResult(
        batch_digests=digests,
        warnings=warnings,
        stage_complete=stage_complete,
        stopped_early=False,
    )


def persist_sample_analysis(
    analysis_root: Path,
    sample_analysis: dict[str, Any],
) -> Path:
    payload = dict(sample_analysis)
    for path_key in _SAMPLE_ANALYSIS_PATH_KEYS:
        payload.pop(path_key, None)
    audio_profile = payload.get("audioProfile")
    if isinstance(audio_profile, dict) and "energyTimeline" in audio_profile:
        slimmed = slim_audio_profile(audio_profile)
        if slimmed is not None:
            payload["audioProfile"] = slimmed
    digests = payload.get("keyframeBatchDigests")
    if isinstance(digests, list) and any(
        isinstance(item, dict) and ("visualFacts" in item or "frames" in item)
        for item in digests
    ):
        payload["keyframeBatchDigests"] = batch_digest_index_entries(
            [item for item in digests if isinstance(item, dict)]
        )
    path = analysis_root / "sample-analysis.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path
