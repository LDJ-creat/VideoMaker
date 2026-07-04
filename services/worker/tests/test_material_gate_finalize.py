from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.pipelines.material_gate_finalize import finalize_slot_material_gate
from app.pipelines.material_review import material_spec_content_hash
from app.pipelines.material_review_state import load_material_review_state


def _write_spec(generated_root: Path, action_id: str, spec: dict) -> None:
    action_dir = generated_root / action_id
    action_dir.mkdir(parents=True, exist_ok=True)
    (action_dir / "material-spec.json").write_text(json.dumps(spec), encoding="utf-8")


def test_finalize_promotes_approved_marker_without_llm(tmp_path: Path) -> None:
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
    _write_spec(generated_root, action_id, spec)

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
            "agentReviewRound": 1,
        },
    }
    (scratch / "material-review-marker.json").write_text(json.dumps(marker), encoding="utf-8")

    plan = {
        "id": "gen-1",
        "variant": "high_click",
        "completionActions": [
            {"id": action_id, "slotId": slot_id, "provider": "hyperframes_material"},
        ],
        "storyboard": [{"slotId": slot_id, "startSec": 0, "endSec": 9.5}],
    }

    run_slot_review = MagicMock(side_effect=AssertionError("run_slot_review should not be called"))
    with patch("app.pipelines.material_review.run_slot_review", run_slot_review), patch(
        "app.pipelines.material_gate_finalize.check_preview_hard_gates",
        return_value=[],
    ):
        report = finalize_slot_material_gate(
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
            final_source="preview_copy",
        )

    run_slot_review.assert_not_called()
    assert report["approved"] is True
    assert report["reviewInputs"]["reviewReuse"] == "in_session"
    assert report["reviewPhase"] == "promoted"
    state = load_material_review_state(generation_root)
    assert state["slots"][slot_id]["status"] == "agent_passed"


def test_finalize_failed_marker_still_agent_failed_with_preview(tmp_path: Path) -> None:
    generation_root = tmp_path / "gen"
    generated_root = generation_root / "generated"
    action_id = "action-slot-3"
    slot_id = "slot-3"
    generated_root.mkdir(parents=True)
    preview_path = generated_root / f"{action_id}.mp4"
    preview_path.write_bytes(b"\x00" * 20_000)
    spec = {
        "template": "composition",
        "durationSec": 4.0,
        "composition": {"bodyHtml": "<div/>"},
    }
    _write_spec(generated_root, action_id, spec)

    scratch = generation_root / "acp-author" / slot_id
    scratch.mkdir(parents=True)
    marker = {
        "approved": False,
        "specHash": material_spec_content_hash(spec),
        "report": {
            "slotId": slot_id,
            "generationId": "gen-1",
            "approved": False,
            "issues": ["text_too_small"],
            "suggestions": ["Increase font size"],
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

    with patch("app.pipelines.material_review.run_slot_review") as run_slot_review, patch(
        "app.pipelines.material_gate_finalize.check_preview_hard_gates",
        return_value=[],
    ):
        report = finalize_slot_material_gate(
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
            final_source="preview_copy",
        )
        run_slot_review.assert_not_called()

    assert report["approved"] is False
    assert "text_too_small" in report["issues"]
    state = load_material_review_state(generation_root)
    assert state["slots"][slot_id]["status"] == "agent_failed"


def test_finalize_partial_harvest_sets_review_bypass(tmp_path: Path) -> None:
    generation_root = tmp_path / "gen"
    generated_root = generation_root / "generated"
    action_id = "action-slot-7"
    slot_id = "slot-7"
    generated_root.mkdir(parents=True)
    preview_path = generated_root / f"{action_id}.mp4"
    preview_path.write_bytes(b"\x00" * 20_000)
    spec = {
        "template": "composition",
        "durationSec": 3.0,
        "composition": {"bodyHtml": "<div/>"},
    }
    _write_spec(generated_root, action_id, spec)
    plan = {
        "id": "gen-1",
        "completionActions": [
            {"id": action_id, "slotId": slot_id, "provider": "hyperframes_material"},
        ],
    }

    with patch(
        "app.pipelines.material_gate_finalize.check_preview_hard_gates",
        return_value=[],
    ):
        report = finalize_slot_material_gate(
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
            final_source="render",
            partial_harvest=True,
        )
    assert report["reviewBypass"] == "partial_harvest"
    state = load_material_review_state(generation_root)
    assert state["slots"][slot_id]["status"] == "agent_failed"


def test_finalize_missing_preview_sets_hard_gate_failed(tmp_path: Path) -> None:
    generation_root = tmp_path / "gen"
    generated_root = generation_root / "generated"
    action_id = "action-slot-9"
    slot_id = "slot-9"
    generated_root.mkdir(parents=True)
    preview_path = generated_root / f"{action_id}.mp4"
    spec = {
        "template": "composition",
        "durationSec": 3.0,
        "composition": {"bodyHtml": "<div/>"},
    }
    spec_dir = generated_root / action_id
    spec_dir.mkdir()
    (spec_dir / "material-spec.json").write_text(json.dumps(spec), encoding="utf-8")
    plan = {
        "id": "gen-1",
        "completionActions": [
            {"id": action_id, "slotId": slot_id, "provider": "hyperframes_material"},
        ],
    }

    report = finalize_slot_material_gate(
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
    assert report.get("hardGateFailed") is True
    assert "preview_missing_or_empty" in report.get("issues", [])
    state = load_material_review_state(generation_root)
    assert state["slots"][slot_id]["status"] == "hard_gate_failed"
