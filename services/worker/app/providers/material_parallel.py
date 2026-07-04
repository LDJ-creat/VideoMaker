from __future__ import annotations

import logging
import os
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from typing import Any

from app.pipelines.tts_mode import MASTER_TTS_SLOT_ID
from app.providers.material_types import MaterialContext, MaterialResult

logger = logging.getLogger(__name__)


def max_concurrent_material_slots() -> int:
    raw = os.getenv("VIDEOMAKER_MATERIAL_MAX_CONCURRENT_SLOTS", "3")
    try:
        return max(1, int(raw))
    except ValueError:
        return 3


def material_slot_timeout_sec() -> float:
    raw = os.getenv("VIDEOMAKER_MATERIAL_SLOT_TIMEOUT_SEC", "2400")
    try:
        return max(60.0, float(raw))
    except ValueError:
        return 2400.0


def _slot_timeout_result(slot_id: str, *, timeout_sec: float) -> MaterialResult:
    return {
        "ok": False,
        "slotId": slot_id,
        "error": {
            "code": "material_slot_timeout",
            "message": f"Material completion timed out for slot {slot_id} after {int(timeout_sec)}s",
            "retryable": True,
        },
    }


def partition_actions_by_slot(
    actions: list[dict[str, Any]],
    *,
    structure: dict[str, Any],
) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    from app.providers.completion_registry import order_completion_actions

    ordered = order_completion_actions(actions, structure=structure)
    visual_groups: dict[str, list[dict[str, Any]]] = {}
    master_actions: list[dict[str, Any]] = []
    for action in ordered:
        slot_id = str(action.get("slotId") or "")
        if slot_id == MASTER_TTS_SLOT_ID:
            master_actions.append(action)
        else:
            visual_groups.setdefault(slot_id, []).append(action)
    return visual_groups, master_actions


def _sort_results_by_actions(
    results: list[MaterialResult],
    actions: list[dict[str, Any]],
) -> list[MaterialResult]:
    order = {str(action["id"]): index for index, action in enumerate(actions) if action.get("id")}
    return sorted(
        results,
        key=lambda item: (order.get(str(item.get("actionId") or ""), 10**9), str(item.get("actionId") or "")),
    )


def execute_slot_chain(
    slot_id: str,
    actions: list[dict[str, Any]],
    ctx: MaterialContext,
    *,
    only_aigc: bool = True,
) -> list[MaterialResult]:
    from app.providers.completion_registry import _execute_single_action

    import time

    started = time.monotonic()
    results: list[MaterialResult] = []
    for action in actions:
        if ctx.is_cancelled():
            results.append(
                {
                    "ok": False,
                    "actionId": action.get("id"),
                    "slotId": action.get("slotId"),
                    "provider": action.get("provider") or action.get("strategy"),
                    "error": {
                        "code": "material_cancelled",
                        "message": f"Material completion cancelled for slot {slot_id}",
                        "retryable": False,
                    },
                }
            )
            return results
        result = _execute_single_action(action, ctx, only_aigc=only_aigc)
        if result is None:
            continue
        results.append(result)
        if not result.get("ok"):
            if ctx.on_slot_chain_complete is not None:
                ctx.on_slot_chain_complete(slot_id, (time.monotonic() - started) * 1000.0)
            return results
    if ctx.on_slot_chain_complete is not None:
        ctx.on_slot_chain_complete(slot_id, (time.monotonic() - started) * 1000.0)
    return results


def _prepare_slot_context(ctx: MaterialContext) -> MaterialContext:
    """Build per-slot context on the caller thread (avoid import deadlocks in workers)."""
    from app.providers.completion_registry import register_default_providers

    if ctx.gateway_factory is None:
        return ctx
    slot_ctx = ctx.fork_for_slot()
    register_default_providers(slot_ctx)
    return slot_ctx


def execute_completion_plan_parallel(
    actions: list[dict[str, Any]],
    ctx: MaterialContext,
    *,
    fail_fast: bool = True,
    only_aigc: bool = True,
    max_workers: int = 3,
) -> list[MaterialResult]:
    from app.providers.completion_registry import _execute_single_action

    ctx.cancel_event.clear()
    visual_groups, master_actions = partition_actions_by_slot(
        actions,
        structure=ctx.structure,
    )
    results: list[MaterialResult] = []
    if not visual_groups:
        for action in master_actions:
            result = _execute_single_action(action, ctx, only_aigc=only_aigc)
            if result is None:
                continue
            results.append(result)
            if not result.get("ok") and fail_fast:
                return _sort_results_by_actions(results, actions)
        return _sort_results_by_actions(results, actions)

    worker_count = min(max_workers, len(visual_groups))
    use_thread_pool = worker_count > 1 and len(visual_groups) > 1 and ctx.gateway_factory is not None
    if worker_count > 1 and len(visual_groups) > 1 and ctx.gateway_factory is None:
        logger.warning(
            "Parallel material slots require gateway_factory; running visual slots serially "
            "(generation_id=%s)",
            ctx.generation_id,
        )

    slot_contexts = {
        slot_id: _prepare_slot_context(ctx)
        for slot_id in visual_groups
    }
    failed = False

    def _run_visual_slots() -> None:
        nonlocal failed
        for slot_id, slot_actions in visual_groups.items():
            if ctx.is_cancelled():
                failed = True
                return
            slot_results = execute_slot_chain(
                slot_id,
                slot_actions,
                slot_contexts[slot_id],
                only_aigc=only_aigc,
            )
            results.extend(slot_results)
            if fail_fast and any(not item.get("ok") for item in slot_results):
                ctx.request_cancel()
                failed = True
                return

    if not use_thread_pool:
        _run_visual_slots()
        if failed:
            return _sort_results_by_actions(results, actions)
    else:
        slot_timeout_sec = material_slot_timeout_sec()
        overall_timeout = slot_timeout_sec * max(1, len(visual_groups))
        deadline = time.monotonic() + overall_timeout
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = {
                executor.submit(
                    execute_slot_chain,
                    slot_id,
                    slot_actions,
                    slot_contexts[slot_id],
                    only_aigc=only_aigc,
                ): slot_id
                for slot_id, slot_actions in visual_groups.items()
            }
            pending = set(futures.keys())
            while pending:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    failed = True
                    ctx.request_cancel()
                    for pending_future in pending:
                        results.append(
                            _slot_timeout_result(
                                futures[pending_future],
                                timeout_sec=slot_timeout_sec,
                            )
                        )
                    executor.shutdown(wait=False, cancel_futures=True)
                    return _sort_results_by_actions(results, actions)

                done, pending = wait(
                    pending,
                    timeout=remaining,
                    return_when=FIRST_COMPLETED,
                )
                if not done:
                    failed = True
                    ctx.request_cancel()
                    for pending_future in pending:
                        if pending_future.done():
                            try:
                                results.extend(pending_future.result())
                            except Exception:
                                logger.exception(
                                    "Parallel material slot failed during timeout drain generation_id=%s",
                                    ctx.generation_id,
                                )
                            continue
                        results.append(
                            _slot_timeout_result(
                                futures[pending_future],
                                timeout_sec=slot_timeout_sec,
                            )
                        )
                    executor.shutdown(wait=False, cancel_futures=True)
                    return _sort_results_by_actions(results, actions)

                for future in done:
                    if future.cancelled():
                        continue
                    slot_id = futures[future]
                    try:
                        slot_results = future.result()
                    except Exception as exc:
                        logger.exception(
                            "Parallel material slot raised generation_id=%s slot_id=%s",
                            ctx.generation_id,
                            slot_id,
                        )
                        slot_results = [
                            {
                                "ok": False,
                                "slotId": slot_id,
                                "error": {
                                    "code": "material_slot_failed",
                                    "message": str(exc),
                                    "retryable": True,
                                },
                            }
                        ]
                    results.extend(slot_results)
                    if fail_fast and any(not item.get("ok") for item in slot_results):
                        ctx.request_cancel()
                        failed = True
                        for pending_future in pending:
                            results.append(
                                _slot_timeout_result(
                                    futures[pending_future],
                                    timeout_sec=slot_timeout_sec,
                                )
                            )
                        pending.clear()
                        break
            if failed:
                executor.shutdown(wait=False, cancel_futures=True)
                return _sort_results_by_actions(results, actions)

    if failed:
        return _sort_results_by_actions(results, actions)

    for action in master_actions:
        if ctx.is_cancelled():
            break
        result = _execute_single_action(action, ctx, only_aigc=only_aigc)
        if result is None:
            continue
        results.append(result)
        if not result.get("ok") and fail_fast:
            return _sort_results_by_actions(results, actions)
    return _sort_results_by_actions(results, actions)
