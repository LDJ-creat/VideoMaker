from __future__ import annotations

from pathlib import Path

import pytest

from material_disk import material_review_approvable


def test_material_review_approvable_accepts_passed_and_skipped() -> None:
    state = {
        "slots": {
            "slot-1": {"status": "agent_passed"},
            "slot-2": {"status": "skipped"},
        }
    }
    actions = [
        {"slotId": "slot-1", "provider": "hyperframes_material", "id": "action-slot-1"},
        {"slotId": "slot-2", "provider": "stock_media_search", "id": "action-slot-2-stock"},
    ]
    ok, reason = material_review_approvable(state=state, completion_actions=actions)
    assert ok is True
    assert reason == ""


def test_material_review_approvable_accepts_review_unavailable() -> None:
    state = {"slots": {"slot-1": {"status": "review_unavailable"}}}
    actions = [{"slotId": "slot-1", "provider": "hyperframes_material", "id": "a1"}]
    ok, reason = material_review_approvable(state=state, completion_actions=actions)
    assert ok is True
    assert reason == ""


def test_material_review_approvable_accepts_agent_failed_with_artifact(tmp_path: Path) -> None:
    generated_root = tmp_path / "generated"
    generated_root.mkdir()
    action_id = "action-slot-3"
    (generated_root / f"{action_id}.mp4").write_bytes(b"\x00" * 20_000)
    state = {"slots": {"slot-3": {"status": "agent_failed"}}}
    actions = [{"slotId": "slot-3", "provider": "hyperframes_material", "id": action_id}]
    ok, reason = material_review_approvable(
        state=state,
        completion_actions=actions,
        generated_root=generated_root,
    )
    assert ok is True
    assert reason == ""


def test_material_review_approvable_accepts_agent_failed_with_small_preview(tmp_path: Path) -> None:
    generated_root = tmp_path / "generated"
    generated_root.mkdir()
    action_id = "action-slot-3"
    (generated_root / f"{action_id}.mp4").write_bytes(b"\x00" * 1024)
    state = {"slots": {"slot-3": {"status": "agent_failed"}}}
    actions = [{"slotId": "slot-3", "provider": "hyperframes_material", "id": action_id}]
    ok, reason = material_review_approvable(
        state=state,
        completion_actions=actions,
        generated_root=generated_root,
    )
    assert ok is True
    assert reason == ""


def test_material_review_approvable_rejects_missing_terminal_action(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    generated_root = tmp_path / "generated"
    generated_root.mkdir()
    (generated_root / "action-slot-3.mp4").write_bytes(b"\x00" * 20_000)
    state = {"slots": {"slot-3": {"status": "agent_passed"}}}
    actions = [{"slotId": "slot-3", "provider": "hyperframes_material", "id": "action-slot-3"}]
    monkeypatch.setattr("material_disk.terminal_visual_action_by_slot", lambda _actions: {})
    ok, reason = material_review_approvable(
        state=state,
        completion_actions=actions,
        generated_root=generated_root,
    )
    assert ok is False
    assert "terminal completion action" in reason


def test_material_review_approvable_rejects_hard_gate_and_missing() -> None:
    actions = [{"slotId": "slot-1", "provider": "hyperframes_material", "id": "a1"}]
    failed_state = {"slots": {"slot-1": {"status": "hard_gate_failed"}}}
    ok, reason = material_review_approvable(state=failed_state, completion_actions=actions)
    assert ok is False
    assert "hard_gate_failed" in reason or "not ready" in reason

    missing_state = {"slots": {}}
    ok2, reason2 = material_review_approvable(state=missing_state, completion_actions=actions)
    assert ok2 is False
    assert "no review state" in reason2


def test_material_review_approvable_rejects_agent_failed_without_artifact(tmp_path: Path) -> None:
    generated_root = tmp_path / "generated"
    generated_root.mkdir()
    state = {"slots": {"slot-3": {"status": "agent_failed"}}}
    actions = [{"slotId": "slot-3", "provider": "hyperframes_material", "id": "action-slot-3"}]
    ok, reason = material_review_approvable(
        state=state,
        completion_actions=actions,
        generated_root=generated_root,
    )
    assert ok is False
    assert "missing" in reason.lower() or "artifact" in reason.lower()
