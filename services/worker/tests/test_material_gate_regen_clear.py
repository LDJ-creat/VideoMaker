from __future__ import annotations

import json
from pathlib import Path

from app.pipelines.material_review_revise import clear_slot_material_gate_artifacts
from app.pipelines.material_review_state import load_material_review_state
from app.providers.completion_registry import invalidate_material_for_slots


def test_clear_slot_material_gate_artifacts_resets_slot_state(tmp_path: Path) -> None:
    generation_root = tmp_path / "gen"
    generation_root.mkdir()
    slot_id = "slot-1"
    report_dir = generation_root / "material-reviews" / slot_id
    report_dir.mkdir(parents=True)
    (report_dir / "report.json").write_text(json.dumps({"slotId": slot_id}), encoding="utf-8")
    state = {
        "generationId": "gen-1",
        "projectId": "proj",
        "variant": "high_click",
        "status": "approved",
        "slots": {slot_id: {"status": "agent_failed", "latestReportUri": "material-reviews/slot-1/report.json"}},
    }
    (generation_root / "material-review-state.json").write_text(json.dumps(state), encoding="utf-8")

    clear_slot_material_gate_artifacts(generation_root, {slot_id})

    assert not report_dir.exists()
    updated = load_material_review_state(generation_root)
    assert updated["status"] == "draft"
    assert updated["slots"][slot_id]["status"] == "pending"


def test_invalidate_material_for_slots_clears_gate_when_requested(tmp_path: Path) -> None:
    generation_root = tmp_path / "gen"
    generated_root = generation_root / "generated"
    generated_root.mkdir(parents=True)
    slot_id = "slot-2"
    action_id = "action-slot-2"
    clip = generated_root / f"{action_id}.mp4"
    clip.write_bytes(b"\x00" * 20_000)
    report_dir = generation_root / "material-reviews" / slot_id
    report_dir.mkdir(parents=True)
    (report_dir / "report.json").write_text("{}", encoding="utf-8")
    state = {
        "generationId": "gen-1",
        "projectId": "proj",
        "variant": "high_click",
        "status": "draft",
        "slots": {slot_id: {"status": "agent_passed"}},
    }
    (generation_root / "material-review-state.json").write_text(json.dumps(state), encoding="utf-8")
    material_state_path = generation_root / "material-state.json"
    material_state_path.write_text(json.dumps({"videoGenQuota": {}, "completedActionIds": [action_id]}), encoding="utf-8")
    actions = [{"id": action_id, "slotId": slot_id, "provider": "hyperframes_material"}]

    invalidate_material_for_slots(
        actions=actions,
        generated_root=generated_root,
        slot_ids={slot_id},
        material_state_path=material_state_path,
        clear_material_gate=True,
        generation_root=generation_root,
    )

    assert not clip.is_file()
    assert not report_dir.exists()
    updated = load_material_review_state(generation_root)
    assert updated["slots"][slot_id]["status"] == "pending"
