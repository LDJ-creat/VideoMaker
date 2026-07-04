from __future__ import annotations

import json
from pathlib import Path

from unittest.mock import patch

from app.pipelines.material_review import enrich_material_review_report, material_spec_content_hash
from app.pipelines.material_review_finalize import persist_slot_material_review
from app.pipelines.material_review_state import load_material_review_state


def test_persist_slot_material_review_reuses_matching_report(tmp_path: Path) -> None:
    generation_root = tmp_path / "projects" / "proj" / "generations" / "gen-1"
    generated_root = generation_root / "generated"
    action_id = "action-slot-5"
    slot_id = "slot-5"
    generated_root.mkdir(parents=True)
    preview_path = generated_root / f"{action_id}.mp4"
    preview_path.write_bytes(b"\x00" * 20_000)

    spec = {
        "template": "composition",
        "durationSec": 9.5,
        "composition": {"bodyHtml": "<div class=\"line\">价值对等</div>"},
    }
    spec_dir = generated_root / action_id
    spec_dir.mkdir()
    (spec_dir / "material-spec.json").write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")

    existing_report = enrich_material_review_report(
        {
            "slotId": slot_id,
            "generationId": "gen-1",
            "approved": True,
            "issues": [],
            "suggestions": [],
            "reviewInputs": {"mode": "video", "videoPath": str(preview_path)},
            "agentReviewRound": 1,
            "provider": "hyperframes_material",
        },
        spec=spec,
        preview_path=preview_path,
    )
    report_dir = generation_root / "material-reviews" / slot_id
    report_dir.mkdir(parents=True)
    (report_dir / "report.json").write_text(json.dumps(existing_report, ensure_ascii=False), encoding="utf-8")

    plan = {
        "id": "gen-1",
        "variant": "high_click",
        "completionActions": [
            {
                "id": action_id,
                "slotId": slot_id,
                "provider": "hyperframes_material",
            }
        ],
        "storyboard": [{"slotId": slot_id, "startSec": 0, "endSec": 9.5}],
    }

    report = persist_slot_material_review(
        generation_root=generation_root,
        generation_id="gen-1",
        project_id="proj",
        variant="high_click",
        action=plan["completionActions"][0],
        plan=plan,
        preview_path=preview_path,
        spec_uri=f"generated/{action_id}/material-spec.json",
        artifact_ref=None,
        storyboard=list(plan["storyboard"]),
        generated_root=generated_root,
    )

    assert report["approved"] is True
    assert report["reviewInputs"]["reviewReuse"] == "report_reused"

    state = load_material_review_state(generation_root)
    assert state["slots"][slot_id]["status"] == "agent_passed"


def test_persist_slot_material_review_promotes_scratch_marker(tmp_path: Path) -> None:
    generation_root = tmp_path / "gen"
    generated_root = generation_root / "generated"
    action_id = "action-slot-8"
    slot_id = "slot-8"
    generated_root.mkdir(parents=True)
    preview_path = generated_root / f"{action_id}.mp4"
    preview_path.write_bytes(b"\x00" * 20_000)
    spec = {
        "template": "composition",
        "durationSec": 5.0,
        "composition": {"bodyHtml": "<div/>"},
    }
    spec_dir = generated_root / action_id
    spec_dir.mkdir()
    (spec_dir / "material-spec.json").write_text(json.dumps(spec), encoding="utf-8")

    scratch = generation_root / "acp-author" / slot_id
    scratch.mkdir(parents=True)
    marker = {
        "approved": True,
        "specHash": material_spec_content_hash(spec),
        "report": {
            "slotId": slot_id,
            "generationId": "gen-1",
            "approved": True,
            "issues": [],
            "suggestions": [],
            "reviewInputs": {"mode": "video"},
        },
    }
    (scratch / "material-review-marker.json").write_text(json.dumps(marker), encoding="utf-8")

    plan = {
        "id": "gen-1",
        "completionActions": [
            {"id": action_id, "slotId": slot_id, "provider": "hyperframes_material"},
        ],
    }

    with patch("app.pipelines.material_gate_finalize.check_preview_hard_gates", return_value=[]):
        report = persist_slot_material_review(
            generation_root=generation_root,
            generation_id="gen-1",
            project_id="proj",
            variant="high_click",
            action=plan["completionActions"][0],
            plan=plan,
            preview_path=preview_path,
            spec_uri=f"generated/{action_id}/material-spec.json",
            artifact_ref=None,
            generated_root=generated_root,
        )
    assert report["reviewInputs"]["reviewReuse"] == "in_session"
    assert report["reviewPhase"] == "promoted"
