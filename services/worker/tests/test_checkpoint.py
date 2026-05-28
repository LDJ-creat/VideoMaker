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
