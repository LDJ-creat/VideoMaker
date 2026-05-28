from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI

from app.db.session import Database, initialize_database
from app.routers.generations import router as generations_router
from app.routers.projects import router as projects_router
from app.routers.samples import router as samples_router
from app.routers.tasks import router as tasks_router
from app.services.pipeline_runner import PipelineRunner
from app.services.project_store import ProjectStore
from app.services.task_events import TaskEventService
from app.settings import Settings


def create_app(
    *,
    database_path: Path | None = None,
    storage_root: Path | None = None,
    sync_pipelines: bool = False,
    pipeline_runner: PipelineRunner | None = None,
) -> FastAPI:
    root = Path.cwd()
    settings = Settings(
        database_path=database_path or root / "storage" / "videomaker.sqlite3",
        storage_root=storage_root or root / "storage",
    )
    database = Database(settings.database_path)
    initialize_database(database)

    task_events = TaskEventService(database)
    project_store = ProjectStore(database)
    runner = pipeline_runner or PipelineRunner(
        database=database,
        storage_root=settings.storage_root,
        task_events=task_events,
        project_store=project_store,
        sync=sync_pipelines,
    )

    app = FastAPI(title="VideoMaker API")
    app.state.settings = settings
    app.state.db = database
    app.state.storage_root = settings.storage_root
    app.state.pipeline_runner = runner

    app.include_router(tasks_router)
    app.include_router(projects_router)
    app.include_router(samples_router)
    app.include_router(generations_router)

    @app.get("/health")
    def health() -> dict[str, bool]:
        return {"ok": True}

    return app
