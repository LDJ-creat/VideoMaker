from __future__ import annotations

from pathlib import Path

from app.pipelines.canonical_narration import invalidate_narration_timing
from app.pipelines.revise_material_edit import resolve_spec_duration_sec
from app.runtime.checkpoint import GenerationCheckpoint, should_skip_planning_completion_resumable


def test_resolve_spec_duration_sec_caps_at_authoritative_window() -> None:
    assert resolve_spec_duration_sec(
        {"durationSec": 8.0},
        fallback_duration_sec=4.0,
        prefer_duration_sec=5.0,
    ) == 5.0


def test_invalidate_narration_timing_unmarks_planning_completion(tmp_path: Path) -> None:
    generation_root = tmp_path / "gen"
    generation_root.mkdir()
    checkpoint = GenerationCheckpoint.load(generation_root / "checkpoint.json")
    checkpoint.mark_stage_complete("planning_completion")
    checkpoint.save(generation_root / "checkpoint.json")
    (generation_root / "narration-timing.json").write_text("{}", encoding="utf-8")

    invalidate_narration_timing(generation_root)

    reloaded = GenerationCheckpoint.load(generation_root / "checkpoint.json")
    assert "planning_completion" not in reloaded.completedStages


def test_should_skip_planning_requires_current_canonical_timing(tmp_path: Path) -> None:
    generation_root = tmp_path / "gen"
    generation_root.mkdir()
    (generation_root / "gap-report.json").write_text('{"gaps":[]}', encoding="utf-8")
    (generation_root / "generation-plan.json").write_text('{"timeline":{"tracks":[]}}', encoding="utf-8")
    (generation_root / "script-draft.json").write_text(
        '{"generationId":"gen-1","masterNarration":"hello","storyboard":[{"slotId":"hook","script":"hello","startSec":0,"endSec":2}],"contentHash":"abc"}',
        encoding="utf-8",
    )
    checkpoint = GenerationCheckpoint.load(generation_root / "checkpoint.json")
    checkpoint.mark_stage_complete("planning_completion")
    checkpoint.save(generation_root / "checkpoint.json")

    assert should_skip_planning_completion_resumable(
        checkpoint,
        generation_root,
        resume=True,
    ) is False
