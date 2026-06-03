from app.runtime.video_gen_quota import VideoGenQuota


def test_consume_per_slot_allows_one_per_slot() -> None:
    quota = VideoGenQuota(max_slots=3, max_per_slot=1)
    assert quota.consume("slot-a") is True
    assert quota.consume("slot-a") is False
    assert quota.consume("slot-b") is True
    assert quota.used == 2


def test_from_checkpoint_restores_consumed_slots() -> None:
    quota = VideoGenQuota.from_checkpoint(
        {
            "maxPerSlot": 1,
            "maxSlots": 2,
            "consumedSlots": {"slot-a": 1},
        }
    )
    assert quota.can_generate_for_slot("slot-a") is False
    assert quota.can_generate_for_slot("slot-b") is True


def test_to_checkpoint_round_trip() -> None:
    quota = VideoGenQuota(max_slots=2, max_per_slot=1)
    quota.consume("slot-1")
    restored = VideoGenQuota.from_checkpoint(quota.to_checkpoint())
    assert restored.consumed_slots == {"slot-1": 1}
    assert restored.max_slots == 2


def test_from_structure_counts_visual_gap_slots() -> None:
    structure = {
        "slots": [
            {"id": "slot1", "role": "hook_visual", "requiredAssetType": ["video"]},
            {"id": "slot2", "role": "usage_scene", "requiredAssetType": ["image"]},
            {"id": "slot3", "role": "hook_text", "requiredAssetType": ["text"]},
        ]
    }
    gap_report = {
        "weakSlots": [{"slotId": "slot2"}],
        "missingSlots": [{"slotId": "slot1"}],
    }
    quota = VideoGenQuota.from_structure(structure, gap_report=gap_report)
    assert quota.max_slots == 2


def test_legacy_max_calls_migration() -> None:
    quota = VideoGenQuota.from_checkpoint({"used": 1, "maxCalls": 1})
    assert quota.can_generate_for_slot("__legacy__") is False
    assert quota.can_generate_for_slot("slot-new") is True
