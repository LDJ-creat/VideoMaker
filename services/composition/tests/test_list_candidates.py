from __future__ import annotations

import json
from pathlib import Path

from composition.patterns.list_candidates import list_composition_pattern_candidates


def _seed_draft(storage_root: Path, project_id: str, generation_id: str, slot_id: str) -> None:
    draft = (
        storage_root
        / "projects"
        / project_id
        / "knowledge"
        / "drafts"
        / "composition"
        / generation_id
        / slot_id
    )
    draft.mkdir(parents=True)
    (draft / "lint-log.json").write_text(json.dumps({"ok": True}), encoding="utf-8")
    (draft / "entry-meta.json").write_text(
        json.dumps({"entryKind": "composition_pattern", "slotRoles": ["benefit_card"], "lintPassed": True}),
        encoding="utf-8",
    )


def test_list_candidates_skips_drafts_without_generation_plan(tmp_path: Path) -> None:
    storage = tmp_path / "storage"
    _seed_draft(storage, "proj-1", "gen-1", "slot-1")
    patterns = list_composition_pattern_candidates(
        storage,
        project_id="proj-1",
        generation_id="gen-1",
    )
    assert patterns == []


def test_list_candidates_requires_hyperframes_material_slot(tmp_path: Path) -> None:
    storage = tmp_path / "storage"
    project_id = "proj-1"
    generation_id = "gen-1"
    slot_id = "slot-1"
    _seed_draft(storage, project_id, generation_id, slot_id)
    gen_root = storage / "projects" / project_id / "generations" / generation_id
    gen_root.mkdir(parents=True)
    (gen_root / "generation-plan.json").write_text(
        json.dumps(
            {
                "storyboard": [{"slotId": slot_id, "role": "benefit_card"}],
                "completionActions": [
                    {"id": "action-1", "slotId": slot_id, "provider": "image_generation"},
                ],
            }
        ),
        encoding="utf-8",
    )
    patterns = list_composition_pattern_candidates(
        storage,
        project_id=project_id,
        generation_id=generation_id,
    )
    assert patterns == []
