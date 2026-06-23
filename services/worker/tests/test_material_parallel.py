from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from app.pipelines.tts_mode import MASTER_TTS_SLOT_ID
from app.providers.completion_registry import (
    MaterialContext,
    execute_completion_plan,
    register_default_providers,
)
from app.providers.material_parallel import (
    _prepare_slot_context,
    execute_slot_chain,
    max_concurrent_material_slots,
    partition_actions_by_slot,
)
from app.runtime.video_gen_quota import VideoGenQuota


def _action(action_id: str, slot_id: str, provider: str = "image_generation") -> dict[str, Any]:
    return {
        "id": action_id,
        "slotId": slot_id,
        "strategy": provider,
        "provider": provider,
        "reason": "test",
        "outputRef": f"completion://{slot_id}/{provider}",
    }


def _make_ctx(tmp_path: Path, **overrides: Any) -> MaterialContext:
    generated_root = tmp_path / "generated"
    generated_root.mkdir(parents=True, exist_ok=True)
    gateway_counter: list[int] = []

    def gateway_factory() -> MagicMock:
        gateway_counter.append(1)
        mock = MagicMock()
        mock.generate_image.return_value = b"\x89PNG\r\n\x1a\n"
        return mock

    defaults: dict[str, Any] = {
        "project_id": "project-1",
        "generation_id": "gen-1",
        "render_root": tmp_path / "renders" / "gen-1",
        "generated_root": generated_root,
        "gateway": MagicMock(),
        "gateway_factory": gateway_factory,
        "quota": VideoGenQuota(max_calls=3),
        "inventory": {"assets": []},
        "slot_matches": [],
        "storyboard": [
            {
                "id": "scene-1",
                "slotId": "slot-a",
                "startSec": 0.0,
                "endSec": 3.0,
                "visual": "a",
                "script": "hello",
                "source": "text_completion",
            }
        ],
        "structure": {
            "slots": [
                {"id": "slot-a", "importance": "must_have", "role": "hook_visual"},
                {"id": "slot-b", "importance": "must_have", "role": "usage_scene"},
            ]
        },
        "emit_progress": lambda *_args, **_kwargs: None,
        "register_artifact": lambda artifact_type, path: {
            "id": "art-1",
            "type": artifact_type,
            "uri": str(Path(path).resolve()),
            "createdAt": "2026-05-29T00:00:00Z",
        },
    }
    defaults.update(overrides)
    ctx = MaterialContext(**defaults)
    ctx._gateway_counter = gateway_counter  # type: ignore[attr-defined]
    return ctx


def test_max_concurrent_material_slots_default() -> None:
    assert max_concurrent_material_slots() >= 1


def test_partition_puts_master_tts_last(tmp_path: Path) -> None:
    structure = {"slots": []}
    actions = [
        _action("tts-1", MASTER_TTS_SLOT_ID, "tts"),
        _action("a1", "slot-a"),
        _action("a2-finish", "slot-a", "hyperframes_material"),
    ]
    visual, master = partition_actions_by_slot(actions, structure=structure)
    assert MASTER_TTS_SLOT_ID not in visual
    assert len(master) == 1
    assert visual["slot-a"][0]["id"] == "a1"
    assert visual["slot-a"][1]["id"] == "a2-finish"


def test_same_slot_finish_after_primary(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("VIDEOMAKER_MATERIAL_MAX_CONCURRENT_SLOTS", "1")
    order: list[str] = []

    ctx = _make_ctx(tmp_path)
    register_default_providers(ctx)

    original_execute = None

    def tracking_execute(action, inner_ctx, *, only_aigc=True):
        from app.providers import completion_registry as cr

        nonlocal original_execute
        if original_execute is None:
            original_execute = cr._execute_single_action.__wrapped__ if hasattr(cr._execute_single_action, "__wrapped__") else None
        order.append(str(action["id"]))
        gateway = inner_ctx.gateway
        gateway.generate_image.return_value = b"\x89PNG\r\n\x1a\n"
        slot_id = str(action.get("slotId"))
        out = tmp_path / "generated" / f"{action['id']}.png"
        out.write_bytes(b"png")
        return {
            "ok": True,
            "actionId": action["id"],
            "slotId": slot_id,
            "provider": action.get("provider"),
            "artifactRef": {"id": action["id"], "type": "image", "uri": str(out.resolve())},
        }

    monkeypatch.setattr(
        "app.providers.completion_registry._execute_single_action",
        tracking_execute,
    )

    actions = [
        _action("stock-1", "slot-a", "stock_media_search"),
        _action("finish-1", "slot-a", "hyperframes_material"),
        _action("other", "slot-b"),
    ]
    execute_completion_plan(actions, ctx)
    assert order.index("stock-1") < order.index("finish-1")


def test_cross_slot_runs_concurrently(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("VIDEOMAKER_MATERIAL_MAX_CONCURRENT_SLOTS", "3")
    active = {"count": 0, "max": 0}
    active_lock = threading.Lock()
    gate = threading.Event()
    proceed = threading.Event()

    ctx = _make_ctx(tmp_path)
    register_default_providers(ctx)

    def slow_execute(action, inner_ctx, *, only_aigc=True):
        slot_id = str(action.get("slotId"))
        with active_lock:
            active["count"] += 1
            active["max"] = max(active["max"], active["count"])
        gate.set()
        if not proceed.wait(timeout=2):
            with active_lock:
                active["count"] -= 1
            return {"ok": False, "actionId": action["id"], "slotId": slot_id, "error": {"code": "timeout"}}
        with active_lock:
            active["count"] -= 1
        out = tmp_path / "generated" / f"{slot_id}.png"
        out.write_bytes(b"png")
        return {
            "ok": True,
            "actionId": action["id"],
            "slotId": slot_id,
            "provider": action.get("provider"),
            "artifactRef": {"id": action["id"], "type": "image", "uri": str(out.resolve())},
        }

    monkeypatch.setattr(
        "app.providers.completion_registry._execute_single_action",
        slow_execute,
    )

    actions = [_action("a1", "slot-a"), _action("b1", "slot-b")]
    thread = threading.Thread(
        target=lambda: execute_completion_plan(actions, ctx),
        daemon=True,
    )
    thread.start()
    try:
        assert gate.wait(timeout=2)
        threading.Event().wait(0.05)
        assert active["max"] >= 2
    finally:
        proceed.set()
        thread.join(timeout=3)


def test_fail_fast_cancels_pending_slots(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("VIDEOMAKER_MATERIAL_MAX_CONCURRENT_SLOTS", "2")

    ctx = _make_ctx(tmp_path)
    register_default_providers(ctx)

    def flaky_execute(action, inner_ctx, *, only_aigc=True):
        slot_id = str(action.get("slotId"))
        if slot_id == "slot-a":
            return {"ok": False, "actionId": action["id"], "slotId": slot_id, "error": {"code": "fail"}}
        out = tmp_path / "generated" / f"{slot_id}.png"
        out.write_bytes(b"png")
        return {
            "ok": True,
            "actionId": action["id"],
            "slotId": slot_id,
            "provider": action.get("provider"),
            "artifactRef": {"id": action["id"], "type": "image", "uri": str(out.resolve())},
        }

    monkeypatch.setattr(
        "app.providers.completion_registry._execute_single_action",
        flaky_execute,
    )

    actions = [_action("a1", "slot-a"), _action("b1", "slot-b"), _action("c1", "slot-c")]
    results = execute_completion_plan(actions, ctx, fail_fast=True)
    assert any(not r.get("ok") for r in results)
    failed_ids = {str(r.get("actionId")) for r in results if not r.get("ok")}
    assert "a1" in failed_ids


def test_fork_for_slot_uses_distinct_gateway(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path)
    register_default_providers(ctx)
    slot_ctx_a = _prepare_slot_context(ctx)
    slot_ctx_b = _prepare_slot_context(ctx)
    chain_a = execute_slot_chain("slot-a", [_action("a1", "slot-a")], slot_ctx_a)
    chain_b = execute_slot_chain("slot-b", [_action("b1", "slot-b")], slot_ctx_b)
    assert chain_a[0]["ok"] is True
    assert chain_b[0]["ok"] is True
    assert len(ctx._gateway_counter) >= 2  # type: ignore[attr-defined]


def test_serial_mode_matches_single_worker(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("VIDEOMAKER_MATERIAL_MAX_CONCURRENT_SLOTS", "1")
    ctx = _make_ctx(
        tmp_path,
        storyboard=[
            {
                "id": "scene-1",
                "slotId": "slot-hook",
                "startSec": 0.0,
                "endSec": 3.0,
                "visual": "hook",
                "script": "hello",
                "source": "text_completion",
            }
        ],
        structure={
            "slots": [
                {
                    "id": "slot-hook",
                    "importance": "must_have",
                    "role": "hook_visual",
                    "requiredAssetType": ["image"],
                }
            ]
        },
    )
    ctx.gateway.generate_image.return_value = b"\x89PNG\r\n\x1a\n"
    register_default_providers(ctx)
    results = execute_completion_plan([_action("action-1", "slot-hook")], ctx)
    assert len(results) == 1
    assert results[0]["ok"] is True
