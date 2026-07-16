from __future__ import annotations

import json
from pathlib import Path

from app.pipelines.material_gate_promote import (
    load_scratch_review_marker,
    materialize_final_to_generated,
    promote_marker_report,
    should_materialize_final,
    should_promote_as_passed,
)
from app.pipelines.material_review import material_spec_content_hash


def test_should_materialize_final_prefers_copy_preview(tmp_path: Path) -> None:
    scratch = tmp_path / "acp-author" / "slot-1"
    scratch.mkdir(parents=True)
    (scratch / "preview.mp4").write_bytes(b"preview")
    spec = {"template": "composition", "durationSec": 5.0}
    assert should_materialize_final(scratch_dir=scratch, spec=spec) == "copy_preview"


def test_should_materialize_final_force_render(tmp_path: Path) -> None:
    scratch = tmp_path / "acp-author" / "slot-1"
    scratch.mkdir(parents=True)
    (scratch / "preview.mp4").write_bytes(b"preview")
    spec = {"template": "composition", "durationSec": 5.0}
    assert should_materialize_final(scratch_dir=scratch, spec=spec, force_render=True) == "render"


def test_should_materialize_final_stale_marker_forces_render(tmp_path: Path) -> None:
    scratch = tmp_path / "acp-author" / "slot-1"
    scratch.mkdir(parents=True)
    (scratch / "preview.mp4").write_bytes(b"preview")
    spec = {"template": "composition", "durationSec": 5.0, "composition": {"bodyHtml": "<div/>"}}
    stale_hash = "deadbeef"
    (scratch / "material-review-marker.json").write_text(
        json.dumps({"specHash": stale_hash, "approved": False, "report": {"specHash": stale_hash}}),
        encoding="utf-8",
    )
    assert should_materialize_final(scratch_dir=scratch, spec=spec) == "render"


def test_materialize_final_copy_preview(tmp_path: Path) -> None:
    scratch = tmp_path / "acp-author" / "slot-1"
    scratch.mkdir(parents=True)
    (scratch / "preview.mp4").write_bytes(b"preview-bytes")
    spec = {"template": "composition", "durationSec": 5.0, "composition": {"bodyHtml": "<div/>"}}
    (scratch / "material-spec.json").write_text(json.dumps(spec), encoding="utf-8")
    generated = tmp_path / "generated"
    result = materialize_final_to_generated(
        scratch_dir=scratch,
        generated_root=generated,
        action_id="action-slot-1",
        spec=spec,
        mode="copy_preview",
    )
    assert result.ok is True
    assert result.final_source == "preview_copy"
    assert (generated / "action-slot-1.mp4").read_bytes() == b"preview-bytes"
    assert (generated / "action-slot-1" / "material-spec.json").is_file()


def test_should_promote_as_passed_requires_approved_marker(tmp_path: Path) -> None:
    spec = {"template": "composition", "durationSec": 5.0}
    spec_hash = material_spec_content_hash(spec)
    assert should_promote_as_passed({"approved": True, "specHash": spec_hash}, spec=spec)
    assert not should_promote_as_passed({"approved": False, "specHash": spec_hash}, spec=spec)
    assert not should_promote_as_passed(None, spec=spec)


def test_promote_marker_report_sets_promoted_trace(tmp_path: Path) -> None:
    preview = tmp_path / "action-slot-1.mp4"
    preview.write_bytes(b"x" * 20_000)
    spec = {"template": "composition", "durationSec": 5.0, "composition": {"bodyHtml": "<div/>"}}
    marker = {
        "approved": True,
        "specHash": material_spec_content_hash(spec),
        "report": {
            "slotId": "slot-1",
            "generationId": "gen-1",
            "approved": True,
            "issues": [],
            "suggestions": [],
            "reviewInputs": {"mode": "video"},
        },
    }
    report = promote_marker_report(
        marker,
        spec=spec,
        final_preview_path=preview,
        generation_id="gen-1",
        slot_id="slot-1",
        provider="hyperframes_material",
        final_source="preview_copy",
    )
    assert report["reviewInputs"]["reviewReuse"] == "in_session"
    assert report["reviewPhase"] == "promoted"
    assert report["finalSource"] == "preview_copy"
    assert report["trace"]["reviewRoute"] == "promoted"


def test_load_scratch_review_marker(tmp_path: Path) -> None:
    generation_root = tmp_path / "gen"
    slot_id = "slot-2"
    scratch = generation_root / "acp-author" / slot_id
    scratch.mkdir(parents=True)
    payload = {"approved": False, "specHash": "abc"}
    (scratch / "material-review-marker.json").write_text(json.dumps(payload), encoding="utf-8")
    loaded = load_scratch_review_marker(generation_root, slot_id)
    assert loaded == payload
