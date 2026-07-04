from __future__ import annotations

import logging
import os
import subprocess
import threading
from typing import Any

logger = logging.getLogger("videomaker.worker")


class WorkerProcessRegistry:
    """Track worker subprocesses by task_id so cancel/retry can terminate them."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._processes: dict[str, subprocess.Popen[Any]] = {}

    def register(self, task_id: str, process: subprocess.Popen[Any]) -> None:
        if not task_id:
            return
        with self._lock:
            existing = self._processes.get(task_id)
            if existing is not None and existing is not process:
                self._terminate_process(existing, task_id, reason="superseded")
            self._processes[task_id] = process

    def unregister(self, task_id: str, process: subprocess.Popen[Any]) -> None:
        if not task_id:
            return
        with self._lock:
            current = self._processes.get(task_id)
            if current is process:
                self._processes.pop(task_id, None)

    def terminate(self, task_id: str, *, reason: str = "cancelled") -> bool:
        if not task_id:
            return False
        with self._lock:
            process = self._processes.pop(task_id, None)
        if process is None:
            return False
        return self._terminate_process(process, task_id, reason=reason)

    def _terminate_process(
        self,
        process: subprocess.Popen[Any],
        task_id: str,
        *,
        reason: str,
    ) -> bool:
        if process.poll() is not None:
            return False
        pid = process.pid
        logger.warning(
            "terminating worker subprocess task_id=%s pid=%s reason=%s",
            task_id,
            pid,
            reason,
        )
        try:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(pid)],
                    check=False,
                    capture_output=True,
                    text=True,
                )
            else:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
        except Exception:
            logger.exception("failed to terminate worker task_id=%s pid=%s", task_id, pid)
            return False
        return True
