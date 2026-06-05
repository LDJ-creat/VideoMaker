from __future__ import annotations

import json
from pathlib import Path

from app.runtime.checkpoint import (
    AnalysisCheckpoint,
    is_analysis_stage_done,
    should_skip_analysis_stage,
)


def test_checkpoint_mark_complete_and_save(tmp_path: Path) -> None:
    path = tmp_path / "checkpoint.json"
    cp = AnalysisCheckpoint(sampleId="sample-1")
    cp.mark_stage_complete("extracting_metadata")
    cp.save(path)

    loaded = AnalysisCheckpoint.load(path)
    assert loaded.sampleId == "sample-1"
    assert loaded.completedStages == ["extracting_metadata"]
    assert loaded.failedStage is None


def test_is_analysis_stage_done_rejects_corrupt_metadata(tmp_path: Path) -> None:
    analysis_root = tmp_path / "analysis"
    analysis_root.mkdir()
    (analysis_root / "metadata.json").write_text("{bad", encoding="utf-8")
    assert is_analysis_stage_done("extracting_metadata", analysis_root) is False


def test_should_skip_when_resume_and_artifacts_valid(tmp_path: Path) -> None:
    analysis_root = tmp_path / "analysis"
    analysis_root.mkdir()
    (analysis_root / "metadata.json").write_text(
        json.dumps({"durationSec": 10.0, "hasAudio": True}),
        encoding="utf-8",
    )
    cp = AnalysisCheckpoint(sampleId="s1", completedStages=["extracting_metadata"])
    assert should_skip_analysis_stage(
        "extracting_metadata",
        cp,
        analysis_root,
        resume=True,
    )


def test_should_not_skip_without_resume(tmp_path: Path) -> None:
    analysis_root = tmp_path / "analysis"
    analysis_root.mkdir()
    (analysis_root / "metadata.json").write_text(json.dumps({"durationSec": 1}), encoding="utf-8")
    cp = AnalysisCheckpoint(completedStages=["extracting_metadata"])
    assert should_skip_analysis_stage("extracting_metadata", cp, analysis_root, resume=False) is False


def test_visual_facts_stage_done_with_partial_batch_coverage(tmp_path: Path, monkeypatch) -> None:
    analysis_root = tmp_path / "analysis"
    analysis_root.mkdir()
    digest_dir = analysis_root / "batch-digests"
    digest_dir.mkdir()
    (digest_dir / "batch-0.json").write_text(
        json.dumps({"batchIndex": 0, "startSec": 0, "endSec": 8, "frames": [], "visualFacts": "x", "onScreenTextFacts": []}),
        encoding="utf-8",
    )
    (digest_dir / "batch-1.json").write_text(
        json.dumps({"batchIndex": 1, "startSec": 8, "endSec": 16, "frames": [], "visualFacts": "y", "onScreenTextFacts": []}),
        encoding="utf-8",
    )
    (digest_dir / "batch-2.json").write_text(
        json.dumps({"batchIndex": 2, "startSec": 16, "endSec": 24, "frames": [], "visualFacts": "z", "onScreenTextFacts": []}),
        encoding="utf-8",
    )
    (analysis_root / "visual-facts-progress.json").write_text(
        json.dumps({"totalBatches": 4, "completedIndices": [0, 1, 2], "failedIndices": [3]}),
        encoding="utf-8",
    )
    monkeypatch.setenv("VIDEOMAKER_VISION_BATCH_MIN_COVERAGE", "0.67")
    assert is_analysis_stage_done("extracting_visual_facts", analysis_root) is True
