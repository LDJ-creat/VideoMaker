from __future__ import annotations

from pathlib import Path

from app.services.pipeline_runner import _augment_worker_env, _shared_root, _worker_root


def test_shared_root_points_at_services_shared() -> None:
    shared = _shared_root()
    worker = _worker_root()
    assert shared.name == "shared"
    assert worker.name == "worker"
    assert shared.parent == worker.parent
    assert (shared / "model_gateway" / "__init__.py").is_file()


def test_augment_worker_env_sets_vm_database_path(tmp_path: Path) -> None:
    db_path = tmp_path / "videomaker.sqlite3"
    env = _augment_worker_env({}, database_path=db_path)
    assert env["VM_DATABASE_PATH"] == str(db_path)
