from __future__ import annotations

from app.pipelines.short_form_direct import (
    filter_short_form_completion_actions,
    simplify_storyboard_for_short_form,
)


def test_simplify_storyboard_for_short_form_merges_to_max_scenes() -> None:
    storyboard = [
        {"id": f"s{i}", "slotId": f"slot-{i}", "startSec": i, "endSec": i + 1, "visual": f"v{i}", "script": f"t{i}"}
        for i in range(6)
    ]
    simplified = simplify_storyboard_for_short_form(storyboard, target_sec=45, max_scenes=3)
    assert len(simplified) == 3
    assert simplified[-1]["endSec"] == 45.0


def test_filter_short_form_completion_actions_keeps_single_video_job() -> None:
    actions = [
        {"slotId": "slot-a", "strategy": "video_generation"},
        {"slotId": "slot-b", "strategy": "video_generation"},
        {"slotId": "slot-a", "strategy": "tts"},
    ]
    filtered = filter_short_form_completion_actions(actions, primary_slot_id="slot-a")
    video_actions = [action for action in filtered if action["strategy"] == "video_generation"]
    assert len(video_actions) == 1
    assert video_actions[0]["slotId"] == "slot-a"
