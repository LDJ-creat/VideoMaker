from __future__ import annotations

import subprocess
import sys
import time
from unittest.mock import MagicMock

from app.services.worker_process_registry import WorkerProcessRegistry


def _sleepy_process() -> subprocess.Popen[str]:
    return subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def test_registry_terminate_removes_process() -> None:
    registry = WorkerProcessRegistry()
    process = _sleepy_process()
    registry.register("task-1", process)
    assert registry.terminate("task-1", reason="test") is True
    assert process.poll() is not None
    assert registry.terminate("task-1", reason="test") is False


def test_registry_supersedes_existing_process() -> None:
    registry = WorkerProcessRegistry()
    first = _sleepy_process()
    second = _sleepy_process()
    registry.register("task-1", first)
    registry.register("task-1", second)
    time.sleep(0.2)
    assert first.poll() is not None
    registry.terminate("task-1", reason="test")
    assert second.poll() is not None


def test_registry_unregister_only_matches_same_process() -> None:
    registry = WorkerProcessRegistry()
    process = _sleepy_process()
    registry.register("task-1", process)
    registry.unregister("task-1", MagicMock())
    assert registry.terminate("task-1", reason="test") is True
    assert process.poll() is not None
