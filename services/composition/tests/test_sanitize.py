from __future__ import annotations

import json
from pathlib import Path

from composition.patterns.sanitize import (
    find_storyboard_scene,
    load_generation_plan_context,
    storyboard_summary_for_slot,
)


def test_storyboard_summary_for_slot() -> None:
    storyboard = [
        {"slotId": "a", "scriptIntent": "hello", "visualIntent": "world"},
    ]
    assert storyboard_summary_for_slot(storyboard, "a") == "hello / world"
    assert find_storyboard_scene(storyboard, "a") is not None


def test_load_generation_plan_context(tmp_path: Path) -> None:
    storage = tmp_path / "storage"
    gen_root = storage / "projects" / "p1" / "generations" / "g1"
    gen_root.mkdir(parents=True)
    (gen_root / "generation-plan.json").write_text(
        json.dumps(
            {
                "masterNarration": "整体旁白",
                "storyboard": [{"slotId": "slot-1", "role": "benefit_card", "scriptIntent": "卖点"}],
                "completionActions": [
                    {"id": "action-1", "slotId": "slot-1", "provider": "hyperframes_material"},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    ctx = load_generation_plan_context(
        storage,
        project_id="p1",
        generation_id="g1",
        slot_id="slot-1",
    )
    assert ctx["slotRole"] == "benefit_card"
    assert ctx["actionId"] == "action-1"
