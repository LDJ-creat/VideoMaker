from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI

from app.db.session import Database, initialize_database
from app.routers.tasks import router as tasks_router
from app.settings import Settings


def create_app(
    *,
    database_path: Path | None = None,
    storage_root: Path | None = None,
) -> FastAPI:
    root = Path.cwd()
    settings = Settings(
        database_path=database_path or root / "storage" / "videomaker.sqlite3",
        storage_root=storage_root or root / "storage",
    )
    database = Database(settings.database_path)
    initialize_database(database)

    app = FastAPI(title="VideoMaker API")
    app.state.settings = settings
    app.state.db = database
    app.state.storage_root = settings.storage_root

    app.include_router(tasks_router)

    @app.get("/health")
    def health() -> dict[str, bool]:
        return {"ok": True}

    return app
