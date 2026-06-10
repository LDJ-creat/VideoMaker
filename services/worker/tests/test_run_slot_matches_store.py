from __future__ import annotations

import json
from pathlib import Path

from app.pipelines.run_slot_matches_store import (
    load_shared_slot_matches,
    resolve_slot_matches_for_run,
    save_shared_slot_matches,
    shared_slot_matches_path,
)


def test_shared_slot_matches_path_stays_under_storage_root(tmp_path: Path) -> None:
    path = shared_slot_matches_path(tmp_path, "project-1", "run-abc")
    assert path.is_relative_to(tmp_path)
    assert path.name == "slot-matches.json"


def test_resolve_slot_matches_runs_mapper_once_per_run(tmp_path: Path) -> None:
    calls = {"count": 0}

    def mapper() -> list[dict]:
        calls["count"] += 1
        return [{"slotId": "slot-a", "matchScore": 0.8, "matchReason": "ok"}]

    first = resolve_slot_matches_for_run(
        storage_root=tmp_path,
        project_id="project-1",
        generation_run_id="run-1",
        run_slot_mapper=mapper,
    )
    second = resolve_slot_matches_for_run(
        storage_root=tmp_path,
        project_id="project-1",
        generation_run_id="run-1",
        run_slot_mapper=mapper,
    )

    assert calls["count"] == 1
    assert first == second
    cached = load_shared_slot_matches(shared_slot_matches_path(tmp_path, "project-1", "run-1"))
    assert cached == first


def test_resolve_slot_matches_without_run_id_always_invokes_mapper(tmp_path: Path) -> None:
    calls = {"count": 0}

    def mapper() -> list[dict]:
        calls["count"] += 1
        return [{"slotId": "slot-a", "matchScore": 0.5, "matchReason": "weak"}]

    resolve_slot_matches_for_run(
        storage_root=tmp_path,
        project_id="project-1",
        generation_run_id=None,
        run_slot_mapper=mapper,
    )
    resolve_slot_matches_for_run(
        storage_root=tmp_path,
        project_id="project-1",
        generation_run_id=None,
        run_slot_mapper=mapper,
    )
    assert calls["count"] == 2


def test_save_and_load_roundtrip(tmp_path: Path) -> None:
    path = shared_slot_matches_path(tmp_path, "p1", "run-2")
    payload = [{"slotId": "s1", "matchScore": 0.9, "matchReason": "fit"}]
    save_shared_slot_matches(path, payload)
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["slotMatches"] == payload
    assert load_shared_slot_matches(path) == payload
