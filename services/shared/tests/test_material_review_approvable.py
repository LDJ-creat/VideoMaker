from __future__ import annotations

from material_disk import material_review_approvable


def test_material_review_approvable_accepts_passed_and_skipped() -> None:
    state = {
        "slots": {
            "hook": {"status": "agent_passed"},
            "usage": {"status": "skipped"},
        }
    }
    actions = [
        {"slotId": "hook", "provider": "hyperframes_material"},
        {"slotId": "usage", "provider": "stock_media_search"},
    ]
    ok, reason = material_review_approvable(state=state, completion_actions=actions)
    assert ok is True
    assert reason == ""


def test_material_review_approvable_accepts_review_unavailable() -> None:
    state = {"slots": {"hook": {"status": "review_unavailable"}}}
    actions = [{"slotId": "hook", "provider": "hyperframes_material"}]
    ok, reason = material_review_approvable(state=state, completion_actions=actions)
    assert ok is True
    assert reason == ""


def test_material_review_approvable_rejects_failed_and_missing() -> None:
    failed_state = {"slots": {"hook": {"status": "agent_failed"}}}
    actions = [{"slotId": "hook", "provider": "hyperframes_material"}]
    ok, reason = material_review_approvable(state=failed_state, completion_actions=actions)
    assert ok is False
    assert "hook" in reason

    missing_state = {"slots": {}}
    ok2, reason2 = material_review_approvable(state=missing_state, completion_actions=actions)
    assert ok2 is False
    assert "hook" in reason2
