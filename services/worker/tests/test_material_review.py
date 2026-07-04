from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.pipelines.material_review import (
    check_preview_hard_gates,
    extract_spec_review_beats,
    material_review_enabled,
    resolve_material_review_route,
    sample_review_timestamps,
    slot_needs_agent_review,
    _resolve_material_review_route_with_reason,
)
from app.pipelines.revise_material_edit import SlotChainKind


def test_extract_spec_review_beats_from_timeline_and_html() -> None:
    spec = {
        "durationSec": 10.0,
        "composition": {
            "timelineScript": 'tl.to(1.5, { opacity: 1 }); tl.from(3.0, { y: 20 });',
            "bodyHtml": '<video data-start="2.0" data-duration="1.0" />',
        },
    }
    beats = extract_spec_review_beats(spec)
    times = [item[0] for item in beats]
    assert 1.5 in times
    assert 3.0 in times
    assert any(abs(value - 2.0) < 0.01 for value in times)


def test_sample_review_timestamps_merges_spec_and_ratio_fill() -> None:
    spec_beats = [(1.0, "spec_timeline"), (1.2, "spec_timeline")]
    sampled = sample_review_timestamps(8.0, spec_beats, max_frames=4)
    assert len(sampled) <= 4
    sources = {item[1] for item in sampled}
    assert "ratio_fill" in sources


def test_sample_review_timestamps_short_clip() -> None:
    sampled = sample_review_timestamps(0.4, [], max_frames=4)
    assert len(sampled) == 1
    assert sampled[0][1] == "ratio_fill"


def test_resolve_material_review_route_store_missing(tmp_path: Path) -> None:
    preview = tmp_path / "clip.mp4"
    preview.write_bytes(b"\x00" * 1024)

    class FakeFFmpeg:
        def probe(self, _path: Path) -> dict:
            return {"durationSec": 5.0}

    import app.pipelines.material_review as module

    original = module.FFmpegTool
    module.FFmpegTool = FakeFFmpeg
    try:
        route, reason = _resolve_material_review_route_with_reason(
            store=None,
            preview_path=preview,
            size_mb=0.001,
            duration=5.0,
        )
        assert route == "text_only"
        assert reason == "store_missing"
        assert resolve_material_review_route(store=None, preview_path=preview) == "text_only"
    finally:
        module.FFmpegTool = original


def test_resolve_material_review_route_video_when_configured(tmp_path: Path) -> None:
    preview = tmp_path / "clip.mp4"
    preview.write_bytes(b"\x00" * 1024)
    store = MagicMock()
    store.get_status.return_value = {
        "providers": {
            "videoUnderstanding": {"configured": True, "hasApiKey": True},
            "vision": {"configured": True, "hasApiKey": True},
        }
    }

    class FakeFFmpeg:
        def probe(self, _path: Path) -> dict:
            return {"durationSec": 5.0}

    import app.pipelines.material_review as module

    original = module.FFmpegTool
    module.FFmpegTool = FakeFFmpeg
    try:
        assert resolve_material_review_route(store=store, preview_path=preview) == "video"
    finally:
        module.FFmpegTool = original


def test_resolve_material_review_route_vision_when_video_too_long(tmp_path: Path) -> None:
    preview = tmp_path / "clip.mp4"
    preview.write_bytes(b"\x00" * 1024)
    store = MagicMock()
    store.get_status.return_value = {
        "providers": {
            "videoUnderstanding": {"configured": True, "hasApiKey": True},
            "vision": {"configured": True, "hasApiKey": True},
        }
    }

    class FakeFFmpeg:
        def probe(self, _path: Path) -> dict:
            return {"durationSec": 45.0}

    import app.pipelines.material_review as module

    original = module.FFmpegTool
    module.FFmpegTool = FakeFFmpeg
    try:
        assert resolve_material_review_route(store=store, preview_path=preview) == "vision"
    finally:
        module.FFmpegTool = original


def test_check_preview_hard_gates_missing_file(tmp_path: Path) -> None:
    missing = tmp_path / "missing.mp4"
    errors = check_preview_hard_gates(missing, expected_duration_sec=8.0)
    assert "preview_missing_or_empty" in errors


def test_slot_needs_agent_review_hf_only() -> None:
    action = {"provider": "hyperframes_material", "slotId": "hook", "id": "action-hook"}
    assert slot_needs_agent_review(action, slot_chain=SlotChainKind.HF_ONLY) is True


def test_slot_needs_agent_review_pure_stock_false() -> None:
    action = {"provider": "stock_media_search", "slotId": "usage", "id": "action-usage"}
    assert slot_needs_agent_review(action, slot_chain=SlotChainKind.STOCK_ONLY) is False


def test_material_review_enabled_default() -> None:
    assert material_review_enabled() is True


def test_report_matches_review_artifacts_requires_spec_and_preview_hash(tmp_path: Path) -> None:
    from app.pipelines.material_review import (
        enrich_material_review_report,
        material_spec_content_hash,
        report_matches_review_artifacts,
    )

    spec = {"template": "composition", "durationSec": 9.5, "composition": {"bodyHtml": "<div/>"}}
    preview = tmp_path / "preview.mp4"
    preview.write_bytes(b"same-bytes")
    report = enrich_material_review_report(
        {"approved": True, "issues": [], "suggestions": []},
        spec=spec,
        preview_path=preview,
    )
    assert report_matches_review_artifacts(report, spec=spec, preview_path=preview)
    mutated_spec = {**spec, "durationSec": 8.0}
    assert not report_matches_review_artifacts(report, spec=mutated_spec, preview_path=preview)
    other_preview = tmp_path / "other.mp4"
    other_preview.write_bytes(b"different")
    assert not report_matches_review_artifacts(report, spec=spec, preview_path=other_preview)
    assert material_spec_content_hash(spec) == report["specHash"]
