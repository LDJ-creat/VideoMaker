from __future__ import annotations

import asyncio
import sys
import warnings
from collections.abc import Coroutine
from typing import Any, TypeVar

T = TypeVar("T")


async def _cancel_all_tasks(loop: asyncio.AbstractEventLoop) -> None:
    current = asyncio.current_task()
    pending = [task for task in asyncio.all_tasks(loop) if task is not current]
    if not pending:
        return
    for task in pending:
        task.cancel()
    await asyncio.gather(*pending, return_exceptions=True)


async def _shutdown_loop(loop: asyncio.AbstractEventLoop) -> None:
    await _cancel_all_tasks(loop)
    try:
        await loop.shutdown_asyncgens()
    except Exception:
        pass
    shutdown_default = getattr(loop, "shutdown_default_executor", None)
    if callable(shutdown_default):
        try:
            await shutdown_default()
        except Exception:
            pass
    if sys.platform == "win32":
        # Proactor transports need one tick to close pipes cleanly on Windows.
        await asyncio.sleep(0)


def run_sync_coro(coro: Coroutine[Any, Any, T]) -> T:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(coro)
        finally:
            try:
                loop.run_until_complete(_shutdown_loop(loop))
            except Exception:
                pass
            asyncio.set_event_loop(None)
            loop.close()
            if sys.platform == "win32":
                warnings.filterwarnings(
                    "ignore",
                    message="unclosed transport",
                    category=ResourceWarning,
                )
    raise RuntimeError("run_sync_coro must be called from a sync worker context")
