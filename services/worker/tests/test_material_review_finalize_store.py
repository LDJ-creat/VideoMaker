from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.pipelines.material_review_finalize import _resolve_gateway_store
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
