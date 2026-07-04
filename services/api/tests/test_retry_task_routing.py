from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from app.db.session import Database, initialize_database
from app.services.pipeline_runner import PipelineRunner
from app.services.project_store import ProjectStore
from app.services.task_events import TaskEventService


@pytest.fixture()
def runner(tmp_path: Path) -> PipelineRunner:
    db_path = tmp_path / "videomaker.sqlite3"
    storage_root = tmp_path / "storage"
    storage_root.mkdir()
    database = Database(db_path)
    initialize_database(database, storage_root=storage_root)

    return PipelineRunner(
        database=database,
        storage_root=storage_root,
        task_events=TaskEventService(database),
        project_store=ProjectStore(database),
        sync=True,
        pipeline=MagicMock(),
    )


def _seed_generation(
    runner: PipelineRunner,
    *,
    revise_context: dict[str, Any] | None = None,
) -> tuple[str, str, Path]:
    project = runner.project_store.create_project(name="demo")
    project_id = project["id"]
    runner.project_store.save_brief(
        project_id,
        {"topic": "demo", "sellingPoints": [], "mustMention": [], "avoidMention": []},
    )
    sample = runner.project_store.create_sample(
        project_id=project_id,
        source_kind="upload",
        status="analyzed",
    )
    runner.project_store.update_sample(
        sample["id"],
        status="analyzed",
        structure={"id": "struct-1", "sourceVideoId": sample["id"], "slots": []},
    )
    task = runner.task_events.create_task(
        project_id,
        stage="generating_material",
        message="Material generation failed",
    )
    task_id = task["taskId"]
    generation = runner.project_store.create_generation(
        project_id=project_id,
        task_id=task_id,
        status="failed",
        variant="high_click",
    )
    generation_id = generation["id"]
    runner.task_events.update_task(
        task_id,
        status="failed",
        stage="generating_material",
        progress=65,
        message="Material generation failed",
    )
    gen_root = runner.storage_root / "projects" / project_id / "generations" / generation_id
    gen_root.mkdir(parents=True)
    (gen_root / "checkpoint.json").write_text(
        json.dumps({"generationId": generation_id, "completedStages": [], "humanReviewMode": True}),
        encoding="utf-8",
    )
    if revise_context is not None:
        (gen_root / "revise-context.json").write_text(
            json.dumps(revise_context, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return task_id, generation_id, gen_root


def test_retry_material_gate_revise_uses_generation_resume(runner: PipelineRunner) -> None:
    task_id, _generation_id, _gen_root = _seed_generation(
        runner,
        revise_context={
            "materialGateRevise": {
                "source": "material_gate_revise",
                "materialEditMode": "edit",
                "editInstruction": "画面居中",
                "affectedSlotIds": ["slot-6"],
            }
        },
    )
    runner.start_generation = MagicMock()  # type: ignore[method-assign]
    runner.start_revise = MagicMock()  # type: ignore[method-assign]

    runner.retry_task(task_id)

    runner.start_generation.assert_called_once()
    runner.start_revise.assert_not_called()
    assert runner.start_generation.call_args.kwargs["resume"] is True


def test_retry_fork_revise_uses_start_revise(runner: PipelineRunner) -> None:
    task_id, _generation_id, gen_root = _seed_generation(
        runner,
        revise_context={
            "sourceGenerationId": "gen-source",
            "instruction": "hook 更短",
            "affectedSlotIds": ["hook"],
            "materialScope": "scoped",
        },
    )
    (gen_root / "edit-intent.json").write_text(
        json.dumps({"intents": [{"scope": "hook", "instruction": "hook 更短"}]}),
        encoding="utf-8",
    )
    runner.start_generation = MagicMock()  # type: ignore[method-assign]
    runner.start_revise = MagicMock()  # type: ignore[method-assign]

    runner.retry_task(task_id)

    runner.start_revise.assert_called_once()
    runner.start_generation.assert_not_called()
    assert runner.start_revise.call_args.kwargs["source_generation_id"] == "gen-source"
    assert runner.start_revise.call_args.kwargs["resume"] is True
