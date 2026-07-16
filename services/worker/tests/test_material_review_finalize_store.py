from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.pipelines.material_review_finalize import (
    _resolve_gateway_store,
    infer_storage_root_from_generation_root,
    resolve_database_path,
)
from app.runtime.task_context import TaskContext


def test_resolve_gateway_store_from_explicit_database_path(tmp_path: Path) -> None:
    db_path = tmp_path / "videomaker.sqlite3"
    db_path.write_bytes(b"")
    storage_root = tmp_path / "storage"
    storage_root.mkdir()

    store = _resolve_gateway_store(
        None,
        None,
        database_path=db_path,
        storage_root=storage_root,
    )
    assert store is not None
    status = store.get_status()
    assert isinstance(status, dict)
    assert "providers" in status


def test_resolve_gateway_store_from_vm_database_path_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "videomaker.sqlite3"
    db_path.write_bytes(b"")
    storage_root = tmp_path / "storage"
    storage_root.mkdir()
    task_context = TaskContext(
        task_id="task-1",
        project_id="project-1",
        storage_root=storage_root,
    )
    monkeypatch.setenv("VM_DATABASE_PATH", str(db_path))

    store = _resolve_gateway_store(None, task_context)
    assert store is not None


def test_resolve_gateway_store_prefers_gateway_store_attribute() -> None:
    expected = MagicMock()
    gateway = MagicMock()
    gateway.store = expected

    store = _resolve_gateway_store(gateway, None)
    assert store is expected


def test_infer_storage_root_from_generation_root(tmp_path: Path) -> None:
    generation_root = (
        tmp_path
        / "storage"
        / "projects"
        / "project-1"
        / "generations"
        / "gen-1"
    )
    generation_root.mkdir(parents=True)
    inferred = infer_storage_root_from_generation_root(generation_root)
    assert inferred == tmp_path / "storage"


def test_resolve_database_path_from_storage_root_sibling(tmp_path: Path) -> None:
    storage_root = tmp_path / "storage"
    storage_root.mkdir()
    db_path = storage_root / "videomaker.sqlite3"
    db_path.write_bytes(b"")

    resolved = resolve_database_path(None, storage_root=storage_root)
    assert resolved == db_path


def test_resolve_gateway_store_from_generation_root_and_db_sibling(tmp_path: Path) -> None:
    storage_root = tmp_path / "storage"
    generation_root = storage_root / "projects" / "project-1" / "generations" / "gen-1"
    generation_root.mkdir(parents=True)
    db_path = storage_root / "videomaker.sqlite3"
    db_path.write_bytes(b"")

    store = _resolve_gateway_store(
        None,
        None,
        storage_root=storage_root,
        generation_root=generation_root,
    )
    assert store is not None
    status = store.get_status()
    assert isinstance(status, dict)
    assert "providers" in status
