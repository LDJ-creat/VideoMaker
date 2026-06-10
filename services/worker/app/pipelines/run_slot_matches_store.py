"""Shared slot matches across variants in one generation run."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from knowledge.paths import assert_under_storage_root, validate_storage_segment


def shared_slot_matches_path(
    storage_root: Path,
    project_id: str,
    generation_run_id: str,
) -> Path:
    safe_project = validate_storage_segment(project_id, field="project_id")
    safe_run = validate_storage_segment(generation_run_id, field="generation_run_id")
    path = (
        storage_root
        / "projects"
        / safe_project
        / "generation-runs"
        / safe_run
        / "slot-matches.json"
    )
    assert_under_storage_root(path, storage_root)
    return path


def _lock_path(payload_path: Path) -> Path:
    return payload_path.with_suffix(".lock")


def load_shared_slot_matches(path: Path) -> list[dict[str, Any]] | None:
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    matches = payload.get("slotMatches") if isinstance(payload, dict) else None
    if not isinstance(matches, list):
        return None
    return [item for item in matches if isinstance(item, dict)]


def save_shared_slot_matches(path: Path, slot_matches: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps({"slotMatches": slot_matches}, indent=2, ensure_ascii=False)
    path.write_text(body, encoding="utf-8")


def resolve_slot_matches_for_run(
    *,
    storage_root: Path,
    project_id: str,
    generation_run_id: str | None,
    run_slot_mapper: Callable[[], list[dict[str, Any]]],
    lock_wait_sec: float = 30.0,
    poll_interval_sec: float = 0.25,
) -> list[dict[str, Any]]:
    """Return run-shared slot matches, computing once per generation run when possible."""
    if not generation_run_id:
        return run_slot_mapper()

    payload_path = shared_slot_matches_path(storage_root, project_id, generation_run_id)
    existing = load_shared_slot_matches(payload_path)
    if existing is not None:
        return existing

    lock_path = _lock_path(payload_path)
    deadline = time.monotonic() + lock_wait_sec
    acquired = False
    while time.monotonic() < deadline:
        cached = load_shared_slot_matches(payload_path)
        if cached is not None:
            return cached
        try:
            lock_path.parent.mkdir(parents=True, exist_ok=True)
            lock_path.open("x").close()
            acquired = True
            break
        except FileExistsError:
            time.sleep(poll_interval_sec)

    if not acquired:
        cached = load_shared_slot_matches(payload_path)
        if cached is not None:
            return cached
        return run_slot_mapper()

    try:
        cached = load_shared_slot_matches(payload_path)
        if cached is not None:
            return cached
        slot_matches = run_slot_mapper()
        save_shared_slot_matches(payload_path, slot_matches)
        return slot_matches
    finally:
        lock_path.unlink(missing_ok=True)
