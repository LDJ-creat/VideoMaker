from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.agents.runner import AgentRunner
from app.gateway.providers.base import GatewayError
from app.perception.sample_facts import run_visual_facts_extraction
from app.perception.visual_facts_progress import (
    is_visual_facts_stage_complete,
    load_batch_digest,
    save_batch_digest,
)
from app.runtime.checkpoint import (
    AnalysisCheckpoint,
    is_analysis_stage_done,
    should_skip_analysis_stage,
)
from app.perception.visual_facts_progress import (
    has_pending_visual_facts_batches,
    visual_facts_coverage_met,
)
from app.runtime.task_context import TaskContext
from app.tools.llm_tool import LLMTool


def _sample_analysis(keyframe_count: int = 24) -> dict:
    keyframes = [
        {
            "shotId": f"shot-{index}",
            "timeSec": float(index * 3),
            "path": f"keyframes/frame-{index:03d}.jpg",
            "score": 0.9,
        }
        for index in range(keyframe_count)
    ]
    shots = [
        {
            "startSec": float(index * 3),
            "endSec": float((index + 1) * 3),
            "confidence": 0.9,
            "changeReason": "histogram_cut",
        }
        for index in range(keyframe_count)
    ]
    return {
        "metadata": {"durationSec": float(keyframe_count * 3), "hasAudio": True},
        "transcript": {"segments": []},
        "shots": shots,
        "keyframes": keyframes,
        "locale": "zh",
    }


def _runner() -> AgentRunner:
    return AgentRunner(
        llm=LLMTool(fixture_mode=True, fixtures={}),
        prompt_loader=MagicMock(),
        observability_sink=MagicMock(),
        model_name="fixture",
    )


def _digest(index: int) -> dict:
    start = float(index * 8 * 3)
    end = start + 8.0
    return {
        "batchIndex": index,
        "startSec": start,
        "endSec": end,
        "frames": [],
        "visualFacts": f"facts-{index}",
        "onScreenTextFacts": [],
    }


def test_batch_failure_persists_completed_digest_and_warning(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    analysis_root = tmp_path / "analysis"
    analysis_root.mkdir()
    (analysis_root / "keyframes").mkdir()
    sample_analysis = _sample_analysis(24)
    for frame in sample_analysis["keyframes"]:
        image_path = analysis_root / str(frame["path"])
        image_path.parent.mkdir(parents=True, exist_ok=True)
        image_path.write_bytes(b"fake")

    calls: list[int] = []

    def _fake_batch(runner, *, batch_index: int, **kwargs):
        calls.append(batch_index)
        if batch_index == 1:
            raise GatewayError(code="quota", message="quota exceeded", retryable=True)
        return _digest(batch_index)

    monkeypatch.setattr(
        "app.perception.sample_facts.run_keyframe_batch_analyst",
        _fake_batch,
    )
    monkeypatch.setenv("VIDEOMAKER_VISION_BATCH_MAX_CALLS", "3")
    monkeypatch.setenv("VIDEOMAKER_KEYFRAME_MAX_PER_VIDEO", "24")

    context = TaskContext(project_id="p1", task_id="t1", storage_root=tmp_path)
    result = run_visual_facts_extraction(
        _runner(),
        sample_analysis=sample_analysis,
        analysis_root=analysis_root,
        context=context,
    )

    assert calls == [0, 1]
    assert load_batch_digest(analysis_root, 0) is not None
    assert load_batch_digest(analysis_root, 1) is None
    assert result.stopped_early is True
    assert any("vision_batch_1_failed" in item for item in result.warnings)
    assert any("quota" in item for item in result.warnings)
    assert len(result.batch_digests) == 1

    sample_path = analysis_root / "sample-analysis.json"
    persisted = json.loads(sample_path.read_text(encoding="utf-8"))
    digests = persisted.get("keyframeBatchDigests") or []
    assert len(digests) == 1
    assert digests[0].get("digestRef") == "batch-digests/batch-0.json"
    assert "visualFacts" not in digests[0]
    assert any("vision_batch_1_failed" in item for item in persisted.get("warnings") or [])


def test_resume_skips_completed_batches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    analysis_root = tmp_path / "analysis"
    analysis_root.mkdir()
    save_batch_digest(analysis_root, 0, _digest(0))

    calls: list[int] = []

    def _fake_batch(runner, *, batch_index: int, **kwargs):
        calls.append(batch_index)
        return _digest(batch_index)

    monkeypatch.setattr(
        "app.perception.sample_facts.run_keyframe_batch_analyst",
        _fake_batch,
    )
    monkeypatch.setenv("VIDEOMAKER_VISION_BATCH_MAX_CALLS", "3")
    monkeypatch.setenv("VIDEOMAKER_KEYFRAME_MAX_PER_VIDEO", "24")

    sample_analysis = _sample_analysis(24)
    for frame in sample_analysis["keyframes"]:
        image_path = analysis_root / str(frame["path"])
        image_path.parent.mkdir(parents=True, exist_ok=True)
        image_path.write_bytes(b"fake")

    context = TaskContext(project_id="p1", task_id="t1", storage_root=tmp_path)
    run_visual_facts_extraction(
        _runner(),
        sample_analysis=sample_analysis,
        analysis_root=analysis_root,
        context=context,
    )

    assert 0 not in calls
    assert calls == [1, 2]


def test_partial_coverage_marks_stage_complete(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    analysis_root = tmp_path / "analysis"
    analysis_root.mkdir()
    save_batch_digest(analysis_root, 0, _digest(0))
    save_batch_digest(analysis_root, 1, _digest(1))
    save_batch_digest(analysis_root, 2, _digest(2))

    (analysis_root / "visual-facts-progress.json").write_text(
        json.dumps(
            {
                "totalBatches": 4,
                "completedIndices": [0, 1, 2],
                "failedIndices": [3],
                "lastError": "quota",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("VIDEOMAKER_VISION_BATCH_MIN_COVERAGE", "0.67")

    assert is_visual_facts_stage_complete(analysis_root, total_batches=4) is True
    assert is_analysis_stage_done("extracting_visual_facts", analysis_root) is True


def test_two_of_three_batches_do_not_meet_default_coverage() -> None:
    assert visual_facts_coverage_met(2, 3, min_ratio=0.67) is False
    assert visual_facts_coverage_met(3, 4, min_ratio=0.67) is True


def test_should_not_skip_visual_facts_when_pending_batches_remain(tmp_path: Path) -> None:
    analysis_root = tmp_path / "analysis"
    analysis_root.mkdir()
    (analysis_root / "visual-facts-progress.json").write_text(
        json.dumps({"totalBatches": 3, "completedIndices": [0], "failedIndices": [1]}),
        encoding="utf-8",
    )
    checkpoint = AnalysisCheckpoint(completedStages=["extracting_visual_facts"])
    assert has_pending_visual_facts_batches(analysis_root) is True
    assert should_skip_analysis_stage(
        "extracting_visual_facts",
        checkpoint,
        analysis_root,
        resume=True,
    ) is False


def test_unexpected_batch_failure_still_persists_completed_digest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    analysis_root = tmp_path / "analysis"
    analysis_root.mkdir()
    sample_analysis = _sample_analysis(24)
    for frame in sample_analysis["keyframes"]:
        image_path = analysis_root / str(frame["path"])
        image_path.parent.mkdir(parents=True, exist_ok=True)
        image_path.write_bytes(b"fake")

    calls: list[int] = []

    def _fake_batch(runner, *, batch_index: int, **kwargs):
        calls.append(batch_index)
        if batch_index == 0:
            return _digest(0)
        raise RuntimeError("unexpected encoder failure")

    monkeypatch.setattr(
        "app.perception.sample_facts.run_keyframe_batch_analyst",
        _fake_batch,
    )
    monkeypatch.setenv("VIDEOMAKER_VISION_BATCH_MAX_CALLS", "3")
    monkeypatch.setenv("VIDEOMAKER_KEYFRAME_MAX_PER_VIDEO", "24")

    context = TaskContext(project_id="p1", task_id="t1", storage_root=tmp_path)
    result = run_visual_facts_extraction(
        _runner(),
        sample_analysis=sample_analysis,
        analysis_root=analysis_root,
        context=context,
    )

    assert load_batch_digest(analysis_root, 0) is not None
    assert result.stopped_early is True
    assert any("unexpected encoder failure" in item for item in result.warnings)
