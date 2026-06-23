from __future__ import annotations

import os
import threading
from typing import Any

import pytest

from app.db.session import Database
from app.services.pipeline_runner import PipelineRunner
from app.services.project_store import ProjectStore
from app.services.task_events import TaskEventService


class BlockingGenerationPipeline:
    def __init__(self) -> None:
        self.started_count = 0
        self.started_lock = threading.Lock()
        self.block = threading.Event()
        self.release = threading.Event()

    def run_generation(
        self,
        *,
        project_id: str,
        task_id: str,
        generation_id: str,
        structure: dict[str, Any],
        user_brief: dict[str, Any],
        assets: list[dict[str, Any]],
        emit: Any,
        resume: bool = False,
        variant: str = "default",
        sample_selection: dict[str, Any] | None = None,
        generation_run_id: str | None = None,
        human_review_mode: bool | None = None,
    ) -> dict[str, Any]:
        with self.started_lock:
            self.started_count += 1
        self.block.set()
        self.release.wait(timeout=5)
        return {
            "ok": True,
            "inventory": {"id": "inv-1"},
            "gapReport": {},
            "plan": {"id": generation_id},
        }


@pytest.fixture()
def runner_with_blocking_pipeline(app_paths, monkeypatch):
    monkeypatch.setenv("VIDEOMAKER_MAX_CONCURRENT_GENERATIONS", "2")
    database_path = app_paths["database_path"]
    storage_root = app_paths["storage_root"]
    from app.db.session import Database, initialize_database

    database = Database(database_path)
    initialize_database(database, storage_root=storage_root)
    task_events = TaskEventService(database)
    project_store = ProjectStore(database)
    pipeline = BlockingGenerationPipeline()
    runner = PipelineRunner(
        database=database,
        storage_root=storage_root,
        task_events=task_events,
        project_store=project_store,
        sync=False,
        pipeline=pipeline,
    )
    return runner, pipeline, project_store, task_events


def _start_generation(
    runner: PipelineRunner,
    project_store: ProjectStore,
    task_events: TaskEventService,
    project_id: str,
    *,
    suffix: str,
) -> str:
    task = task_events.create_task(project_id, stage="analyzing_assets", message="Queued")
    generation = project_store.create_generation(
        project_id=project_id,
        task_id=task["taskId"],
        status="queued",
        variant=f"variant-{suffix}",
    )
    runner.start_generation(
        project_id=project_id,
        generation_id=generation["id"],
        task_id=task["taskId"],
        structure={"id": "struct-1", "slots": []},
        user_brief={"topic": "test"},
        assets=[],
    )
    return task["taskId"]


def test_generation_queue_holds_third_job_until_slot_frees(
    runner_with_blocking_pipeline,
) -> None:
    runner, pipeline, project_store, task_events = runner_with_blocking_pipeline
    project = project_store.create_project(name="Concurrency")
    project_id = project["id"]

    _start_generation(runner, project_store, task_events, project_id, suffix="1")
    _start_generation(runner, project_store, task_events, project_id, suffix="2")
    deadline = threading.Event()
    for _ in range(50):
        if pipeline.started_count >= 2:
            break
        threading.Event().wait(0.05)
    assert pipeline.started_count == 2
    assert runner.generation_active_count == 2

    task_id_3 = _start_generation(runner, project_store, task_events, project_id, suffix="3")
    assert runner.generation_queue_size == 1
    assert pipeline.started_count == 2

    task_3 = task_events.get_task(task_id_3)
    assert task_3 is not None
    assert task_3.get("status") == "queued"
    assert "generation slot" in str(task_3.get("message", "")).lower()

    pipeline.release.set()
    threading.Event().wait(0.3)
    pipeline.release.set()
    threading.Event().wait(0.5)

    assert pipeline.started_count == 3
    assert runner.generation_queue_size == 0


def test_generation_cap_one_serializes_variants(app_paths, monkeypatch) -> None:
    monkeypatch.setenv("VIDEOMAKER_MAX_CONCURRENT_GENERATIONS", "1")
    database_path = app_paths["database_path"]
    storage_root = app_paths["storage_root"]
    from app.db.session import Database, initialize_database

    database = Database(database_path)
    initialize_database(database, storage_root=storage_root)
    task_events = TaskEventService(database)
    project_store = ProjectStore(database)
    order: list[str] = []
    order_lock = threading.Lock()

    class OrderedPipeline:
        def run_generation(self, **kwargs: Any) -> dict[str, Any]:
            gid = str(kwargs["generation_id"])
            with order_lock:
                order.append(gid)
            return {
                "ok": True,
                "inventory": {"id": "inv-1"},
                "gapReport": {},
                "plan": {"id": gid},
            }

    runner = PipelineRunner(
        database=database,
        storage_root=storage_root,
        task_events=task_events,
        project_store=project_store,
        sync=True,
        pipeline=OrderedPipeline(),
    )
    project = project_store.create_project(name="Serial")
    project_id = project["id"]
    gen_ids: list[str] = []
    for suffix in ("a", "b"):
        task = task_events.create_task(project_id, stage="analyzing_assets", message="Queued")
        generation = project_store.create_generation(
            project_id=project_id,
            task_id=task["taskId"],
            status="queued",
            variant=suffix,
        )
        gen_ids.append(generation["id"])
        runner.start_generation(
            project_id=project_id,
            generation_id=generation["id"],
            task_id=task["taskId"],
            structure={"id": "struct-1", "slots": []},
            user_brief={"topic": "test"},
            assets=[],
        )
    assert order == gen_ids


def test_duplicate_task_id_not_started_twice(app_paths, monkeypatch) -> None:
    monkeypatch.setenv("VIDEOMAKER_MAX_CONCURRENT_GENERATIONS", "2")
    database_path = app_paths["database_path"]
    storage_root = app_paths["storage_root"]
    from app.db.session import Database, initialize_database

    database = Database(database_path)
    initialize_database(database, storage_root=storage_root)
    task_events = TaskEventService(database)
    project_store = ProjectStore(database)
    release = threading.Event()
    calls = {"count": 0}
    calls_lock = threading.Lock()

    class BlockingPipeline:
        def run_generation(self, **kwargs: Any) -> dict[str, Any]:
            with calls_lock:
                calls["count"] += 1
            release.wait(timeout=2)
            return {
                "ok": True,
                "inventory": {"id": "inv-1"},
                "gapReport": {},
                "plan": {},
            }

    runner = PipelineRunner(
        database=database,
        storage_root=storage_root,
        task_events=task_events,
        project_store=project_store,
        sync=False,
        pipeline=BlockingPipeline(),
    )
    project = project_store.create_project(name="Dup")
    task = task_events.create_task(project["id"], stage="analyzing_assets", message="Queued")
    generation = project_store.create_generation(
        project_id=project["id"],
        task_id=task["taskId"],
        status="queued",
    )
    kwargs = dict(
        project_id=project["id"],
        generation_id=generation["id"],
        task_id=task["taskId"],
        structure={"id": "s1", "slots": []},
        user_brief={},
        assets=[],
    )
    runner.start_generation(**kwargs)
    threading.Event().wait(0.1)
    runner.start_generation(**kwargs)
    assert calls["count"] == 1
    assert runner.generation_active_count == 1
    release.set()
    threading.Event().wait(0.2)
    assert runner.generation_active_count == 0


def test_enqueue_skips_duplicate_task_id(app_paths, monkeypatch) -> None:
    monkeypatch.setenv("VIDEOMAKER_MAX_CONCURRENT_GENERATIONS", "2")
    database_path = app_paths["database_path"]
    storage_root = app_paths["storage_root"]
    from app.db.session import Database, initialize_database

    database = Database(database_path)
    initialize_database(database, storage_root=storage_root)
    task_events = TaskEventService(database)
    project_store = ProjectStore(database)

    class NoopPipeline:
        def run_generation(self, **kwargs: Any) -> dict[str, Any]:
            return {"ok": True, "inventory": {"id": "i"}, "gapReport": {}, "plan": {}}

    runner = PipelineRunner(
        database=database,
        storage_root=storage_root,
        task_events=task_events,
        project_store=project_store,
        sync=True,
        pipeline=NoopPipeline(),
    )
    project = project_store.create_project(name="Dedupe")
    task = task_events.create_task(project["id"], stage="analyzing_assets", message="Queued")
    generation = project_store.create_generation(
        project_id=project["id"],
        task_id=task["taskId"],
        status="queued",
    )
    kwargs = dict(
        project_id=project["id"],
        generation_id=generation["id"],
        task_id=task["taskId"],
        structure={"id": "s1", "slots": []},
        user_brief={},
        assets=[],
    )
    runner.start_generation(**kwargs)
    runner.start_generation(**kwargs)
    assert runner.generation_queue_size == 0
    assert runner.generation_active_count == 0
