from __future__ import annotations

from pathlib import Path

from app.services.pipeline_runner import _shared_root, _worker_root


def test_shared_root_points_at_services_shared() -> None:
    shared = _shared_root()
    worker = _worker_root()
    assert shared.name == "shared"
    assert worker.name == "worker"
    assert shared.parent == worker.parent
    assert (shared / "model_gateway" / "__init__.py").is_file()
