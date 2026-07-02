from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from app.pipelines.material_review_finalize import finalize_visual_material_reviews
from app.pipelines.material_review_state import load_material_review_state


def test_finalize_visual_material_reviews_writes_skipped_for_stock_slot(tmp_path: Path) -> None:
    generation_root = tmp_path / "projects" / "proj" / "generations" / "gen-1"
    generated_root = generation_root / "generated"
    generated_root.mkdir(parents=True)
    slot_id = "usage"
    action_id = "action-usage-stock"
    (generated_root / f"{slot_id}-stock.mp4").write_bytes(b"\x00" * 256)
    plan = {
        "id": "gen-1",
        "variant": "high_click",
        "completionActions": [
            {
                "id": action_id,
                "slotId": slot_id,
                "provider": "stock_media_search",
            }
        ],
        "storyboard": [
            {
                "slotId": slot_id,
                "startSec": 0,
                "endSec": 4,
            }
        ],
    }
    structure = {"slots": [{"id": slot_id, "role": "usage_scene"}]}

    finalize_visual_material_reviews(
        generation_root=generation_root,
        plan=plan,
        project_id="proj",
        variant="high_click",
        structure=structure,
        storyboard=list(plan["storyboard"]),
        generated_root=generated_root,
        gateway=MagicMock(),
        runner=None,
        task_context=None,
    )

    state = load_material_review_state(generation_root)
    assert isinstance(state, dict)
    entry = state["slots"][slot_id]
    assert entry["status"] == "skipped"
    report_path = generation_root / "material-reviews" / slot_id / "report.json"
    assert report_path.is_file()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["reviewInputs"]["mode"] == "skipped"
