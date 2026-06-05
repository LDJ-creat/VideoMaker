from __future__ import annotations

import json
import os
import math
from pathlib import Path
from typing import Any

BATCH_DIGESTS_DIR = "batch-digests"
PROGRESS_FILENAME = "visual-facts-progress.json"


def _batch_coverage_min() -> float:
    raw = os.environ.get("VIDEOMAKER_VISION_BATCH_MIN_COVERAGE", "0.67").strip()
    try:
        return max(0.0, min(1.0, float(raw)))
    except ValueError:
        return 0.67


def batch_digest_path(analysis_root: Path, batch_index: int) -> Path:
    return analysis_root / BATCH_DIGESTS_DIR / f"batch-{batch_index}.json"


def load_batch_digest(analysis_root: Path, batch_index: int) -> dict[str, Any] | None:
    path = batch_digest_path(analysis_root, batch_index)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def save_batch_digest(analysis_root: Path, batch_index: int, digest: dict[str, Any]) -> Path:
    directory = analysis_root / BATCH_DIGESTS_DIR
    directory.mkdir(parents=True, exist_ok=True)
    path = batch_digest_path(analysis_root, batch_index)
    path.write_text(json.dumps(digest, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def load_all_batch_digests(analysis_root: Path) -> list[dict[str, Any]]:
    progress = load_visual_facts_progress(analysis_root)
    total = int(progress.get("totalBatches") or 0) if progress else 0
    if total > 0:
        return load_existing_digests(analysis_root, total)
    directory = analysis_root / BATCH_DIGESTS_DIR
    if not directory.is_dir():
        return []
    digests: list[dict[str, Any]] = []
    for path in sorted(directory.glob("batch-*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            digests.append(data)
    digests.sort(key=lambda item: int(item.get("batchIndex", 0)))
    return digests


def load_existing_digests(analysis_root: Path, total_batches: int) -> list[dict[str, Any]]:
    digests: list[dict[str, Any]] = []
    for index in range(total_batches):
        digest = load_batch_digest(analysis_root, index)
        if digest is not None:
            digests.append(digest)
    return digests


def default_progress(total_batches: int) -> dict[str, Any]:
    return {
        "totalBatches": total_batches,
        "completedIndices": [],
        "failedIndices": [],
        "lastError": None,
    }


def load_visual_facts_progress(analysis_root: Path) -> dict[str, Any] | None:
    path = analysis_root / PROGRESS_FILENAME
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def save_visual_facts_progress(analysis_root: Path, progress: dict[str, Any]) -> Path:
    path = analysis_root / PROGRESS_FILENAME
    path.write_text(json.dumps(progress, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def sync_progress_from_disk(analysis_root: Path, *, total_batches: int) -> dict[str, Any]:
    progress = load_visual_facts_progress(analysis_root) or default_progress(total_batches)
    progress["totalBatches"] = total_batches
    completed: list[int] = []
    failed = [int(item) for item in progress.get("failedIndices") or [] if str(item).isdigit()]
    for index in range(total_batches):
        if load_batch_digest(analysis_root, index) is not None:
            completed.append(index)
    progress["completedIndices"] = sorted(set(completed))
    progress["failedIndices"] = sorted(
        index for index in failed if index not in progress["completedIndices"]
    )
    return progress


def visual_facts_coverage_met(completed: int, total: int, *, min_ratio: float | None = None) -> bool:
    if total <= 0:
        return True
    if completed >= total:
        return True
    threshold = _batch_coverage_min() if min_ratio is None else min_ratio
    required = math.ceil(total * threshold - 1e-9)
    return completed >= max(1, required)


def visual_facts_coverage_ratio(progress: dict[str, Any]) -> float:
    total = int(progress.get("totalBatches") or 0)
    if total <= 0:
        return 1.0
    completed = len(list(progress.get("completedIndices") or []))
    return completed / total


def has_pending_visual_facts_batches(analysis_root: Path) -> bool:
    progress = load_visual_facts_progress(analysis_root)
    if progress is None:
        return False
    total = int(progress.get("totalBatches") or 0)
    if total <= 0:
        return False
    progress = sync_progress_from_disk(analysis_root, total_batches=total)
    completed = len(list(progress.get("completedIndices") or []))
    if progress.get("failedIndices"):
        return True
    return completed < total


def is_visual_facts_stage_complete(analysis_root: Path, *, total_batches: int | None = None) -> bool:
    if total_batches is None:
        progress = load_visual_facts_progress(analysis_root)
        if progress is None:
            data = _read_sample_analysis(analysis_root)
            if isinstance(data, dict) and data.get("keyframeBatchDigests"):
                return True
            keyframes = _read_json(analysis_root / "keyframes.json")
            return isinstance(keyframes, list) and len(keyframes) <= 8
        total_batches = int(progress.get("totalBatches") or 0)
    if total_batches <= 0:
        return True

    progress = sync_progress_from_disk(analysis_root, total_batches=total_batches)
    completed = len(list(progress.get("completedIndices") or []))
    failed = list(progress.get("failedIndices") or [])

    if completed >= total_batches and not failed:
        return True
    return visual_facts_coverage_met(completed, total_batches)


def _read_json(path: Path) -> Any | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _read_sample_analysis(analysis_root: Path) -> dict[str, Any] | None:
    data = _read_json(analysis_root / "sample-analysis.json")
    return data if isinstance(data, dict) else None
