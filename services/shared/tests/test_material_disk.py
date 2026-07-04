from __future__ import annotations

from pathlib import Path

from material_disk import infer_completed_slot_ids


def test_infer_completed_slot_ids_from_hf_and_finish_outputs(tmp_path: Path) -> None:
    generated = tmp_path / "generated"
    generated.mkdir()
    (generated / "action-slot-1-finish.mp4").write_bytes(b"x" * 20_000)
    (generated / "action-slot-2.mp4").write_bytes(b"x" * 20_000)

    actions = [
        {
            "id": "action-slot-1",
            "slotId": "slot-1",
            "provider": "stock_media_search",
            "strategy": "stock_media_search",
        },
        {
            "id": "action-slot-1-finish",
            "slotId": "slot-1",
            "provider": "hyperframes_material",
            "strategy": "hyperframes_material",
        },
        {
            "id": "action-slot-2",
            "slotId": "slot-2",
            "provider": "hyperframes_material",
            "strategy": "hyperframes_material",
        },
    ]

    assert infer_completed_slot_ids(actions, generated) == ["slot-1", "slot-2"]
