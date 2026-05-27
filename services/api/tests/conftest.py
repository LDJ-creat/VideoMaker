from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def app_paths(tmp_path: Path):
    return {
        "database_path": tmp_path / "videomaker.sqlite3",
        "storage_root": tmp_path / "storage",
    }


@pytest.fixture()
def app(app_paths):
    from app.main import create_app

    return create_app(
        database_path=app_paths["database_path"],
        storage_root=app_paths["storage_root"],
    )


@pytest.fixture()
def client(app):
    return TestClient(app)
