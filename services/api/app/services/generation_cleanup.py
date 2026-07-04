from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from knowledge.paths import validate_storage_segment

from app.db.session import Database
from app.services.generation_run_store import GenerationRunStore
from app.services.project_store import ProjectStore


def list_revise_fork_ids_for_source(
    *,
    project_id: str,
    source_generation_id: str,
    storage_root: Path,
    store: ProjectStore,
) -> list[str]:
    fork_ids: list[str] = []
    for record in store.list_generations_for_project(project_id):
        generation_id = str(record["id"])
        if generation_id == source_generation_id:
            continue
        revise_path = (
            storage_root
            / "projects"
            / project_id
            / "generations"
            / generation_id
            / "revise-context.json"
        )
        if not revise_path.is_file():
            continue
        try:
            revise_context = json.loads(revise_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(revise_context, dict):
            continue
        if str(revise_context.get("sourceGenerationId") or "") == source_generation_id:
            fork_ids.append(generation_id)
    return fork_ids


def _delete_artifacts_for_generation(
    database: Database,
    *,
    project_id: str,
    generation_id: str,
) -> None:
    gen_token = f"/generations/{generation_id}/"
    render_token = f"/renders/{generation_id}/"
    with database.connect() as connection:
        rows = connection.execute(
            """
            SELECT id, uri FROM artifacts
            WHERE project_id = ?
            """,
            (project_id,),
        ).fetchall()
        for row in rows:
            uri = str(row["uri"] or "")
            if gen_token in uri or render_token in uri or uri.endswith(f"/{generation_id}"):
                connection.execute(
                    "DELETE FROM artifacts WHERE id = ?",
                    (str(row["id"]),),
                )


def _delete_task_rows(database: Database, task_id: str | None) -> None:
    if not task_id:
        return
    with database.connect() as connection:
        connection.execute("DELETE FROM task_events WHERE task_id = ?", (task_id,))
        connection.execute("DELETE FROM tasks WHERE id = ?", (task_id,))


def _remove_generation_dirs(
    storage_root: Path,
    *,
    project_id: str,
    generation_id: str,
) -> None:
    project_root = storage_root / "projects" / project_id
    for relative in (
        Path("generations") / generation_id,
        Path("renders") / generation_id,
        Path("knowledge") / "drafts" / "composition" / generation_id,
    ):
        target = project_root / relative
        if target.is_dir():
            shutil.rmtree(target)


def delete_generation_with_artifacts(
    *,
    project_id: str,
    generation_id: str,
    storage_root: Path,
    database: Database,
    store: ProjectStore,
    run_store: GenerationRunStore,
    terminate_task: Any | None = None,
    cascade_forks: bool = True,
) -> list[str]:
    validate_storage_segment(project_id, field="project_id")
    validate_storage_segment(generation_id, field="generation_id")

    record = store.get_generation(generation_id)
    if record is None or str(record.get("projectId")) != project_id:
        raise KeyError(generation_id)

    deleted_ids: list[str] = []
    fork_ids = list_revise_fork_ids_for_source(
        project_id=project_id,
        source_generation_id=generation_id,
        storage_root=storage_root,
        store=store,
    )
    if fork_ids and not cascade_forks:
        raise ValueError("generation_has_revise_forks")

    if cascade_forks:
        for fork_id in fork_ids:
            deleted_ids.extend(
                delete_generation_with_artifacts(
                    project_id=project_id,
                    generation_id=fork_id,
                    storage_root=storage_root,
                    database=database,
                    store=store,
                    run_store=run_store,
                    terminate_task=terminate_task,
                    cascade_forks=True,
                )
            )

    task_id = record.get("taskId")
    if task_id and terminate_task is not None:
        terminate_task(str(task_id))

    _delete_artifacts_for_generation(
        database,
        project_id=project_id,
        generation_id=generation_id,
    )
    _delete_task_rows(database, str(task_id) if task_id else None)

    with database.connect() as connection:
        connection.execute("DELETE FROM generations WHERE id = ?", (generation_id,))

    run_store.remove_generation_from_runs(project_id, generation_id)
    _remove_generation_dirs(
        storage_root,
        project_id=project_id,
        generation_id=generation_id,
    )
    deleted_ids.append(generation_id)
    return deleted_ids
