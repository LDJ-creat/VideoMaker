from __future__ import annotations

from pathlib import Path

from app.providers.completion_registry import (
    expected_output_path,
    invalidate_material_for_slots,
    load_material_state,
)


def test_invalidate_material_for_slots_removes_target_slot_only(tmp_path: Path) -> None:
    generated_root = tmp_path / "generated"
    generated_root.mkdir(parents=True)
    keep_action = {
        "id": "action-slot-1",
        "slotId": "slot-1",
        "provider": "image_generation",
        "strategy": "image_generation",
    }
    drop_action = {
        "id": "action-slot-6",
        "slotId": "slot-6",
        "provider": "hyperframes_material",
        "strategy": "hyperframes_material",
    }
    keep_path = expected_output_path(keep_action, generated_root)
    drop_path = expected_output_path(drop_action, generated_root)
    keep_path.parent.mkdir(parents=True, exist_ok=True)
    keep_path.write_bytes(b"keep")
    drop_path.write_bytes(b"drop")
    hf_dir = generated_root / "action-slot-6" / "composition"
    hf_dir.mkdir(parents=True)
    (hf_dir / "index.html").write_text("<html></html>", encoding="utf-8")

    state_path = tmp_path / "material-state.json"
    state_path.write_text(
        '{"videoGenQuota": {}, "completedActionIds": ["action-slot-1", "action-slot-6"]}',
        encoding="utf-8",
    )

    invalidate_material_for_slots(
        actions=[keep_action, drop_action],
        generated_root=generated_root,
        slot_ids={"slot-6"},
        material_state_path=state_path,
    )

    assert keep_path.is_file()
    assert not drop_path.is_file()
    assert not (generated_root / "action-slot-6").exists()
    _, completed = load_material_state(state_path)
    assert "action-slot-1" in completed
    assert "action-slot-6" not in completed
