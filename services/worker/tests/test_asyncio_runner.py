from __future__ import annotations

import asyncio

from app.composition.acp.asyncio_runner import run_sync_coro


def test_run_sync_coro_returns_value() -> None:
    async def sample() -> str:
        await asyncio.sleep(0)
        return "ok"

    assert run_sync_coro(sample()) == "ok"
