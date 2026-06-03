from __future__ import annotations

from app.pipelines.master_narration import (
    apply_master_narration_to_storyboard,
    split_master_into_clauses,
    split_master_narration_by_duration,
)


def test_split_master_into_clauses() -> None:
    master = "夏天出门怕晒黑？这款防晒轻薄不黏腻。评论区领券下单。"
    clauses = split_master_into_clauses(master)
    assert len(clauses) == 3
    assert clauses[0].startswith("夏天")


def test_split_master_narration_by_duration_respects_scene_order() -> None:
    master = "第一句。第二句比较长一点。第三句收尾。"
    scenes = [
        {"slotId": "s1", "startSec": 0.0, "endSec": 5.0},
        {"slotId": "s2", "startSec": 5.0, "endSec": 25.0},
        {"slotId": "s3", "startSec": 25.0, "endSec": 30.0},
    ]
    splits = split_master_narration_by_duration(master, scenes)
    assert len(splits) == 3
    assert all(split for split in splits)
    assert "".join(splits) == master


def test_apply_master_narration_replaces_direction_script() -> None:
    structure = {
        "slots": [
            {
                "id": "slot1",
                "visualIntent": "Present a catchy headline.",
                "scriptIntent": "Present a catchy headline.",
            }
        ]
    }
    storyboard = [
        {
            "id": "scene1",
            "slotId": "slot1",
            "startSec": 0.0,
            "endSec": 5.0,
            "visual": "开场画面",
            "script": "Present a catchy headline.",
            "source": "generated",
        }
    ]
    master, aligned = apply_master_narration_to_storyboard(
        master_narration="夏天出门怕晒黑？",
        storyboard=storyboard,
        structure=structure,
    )
    assert master == "夏天出门怕晒黑？"
    assert aligned[0]["script"] == "夏天出门怕晒黑？"
