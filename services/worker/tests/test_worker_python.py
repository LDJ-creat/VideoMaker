from __future__ import annotations

from app.runtime.worker_python import describe_worker_python, resolve_worker_python


def test_resolve_worker_python_points_to_existing_interpreter() -> None:
    python = resolve_worker_python()
    assert python.endswith("python.exe") or python.endswith("python")


def test_describe_worker_python_returns_label() -> None:
    label = describe_worker_python(resolve_worker_python())
    assert label
