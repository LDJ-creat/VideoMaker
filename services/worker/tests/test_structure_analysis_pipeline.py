from __future__ import annotations

import json
from pathlib import Path

from app.agents.prompt_loader import PromptLoader
from app.agents.runner import AgentRunner
from app.observability.sink import build_observability_sink
from app.pipelines.structure_analysis_pipeline import run_structure_analysis_pipeline
from app.runtime.checkpoint import AnalysisCheckpoint
from app.runtime.task_context import TaskContext
from app.tools.llm_tool import LLMTool, load_agent_fixtures


def _sample_analysis() -> dict:
    path = Path(__file__).parent / "fixtures" / "sample_analysis.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_structure_pipeline_resumes_after_proposing_segments(tmp_path: Path) -> None:
    fixtures = load_agent_fixtures(Path(__file__).parent / "fixtures" / "agents")
    runner = AgentRunner(
        llm=LLMTool(fixture_mode=True, fixtures=fixtures),
        prompt_loader=PromptLoader(),
        observability_sink=build_observability_sink(tmp_path),
        model_name="fixture",
    )
    analysis_root = tmp_path / "analysis"
    analysis_root.mkdir(parents=True)
    proposal = json.loads(
        (Path(__file__).parent / "fixtures" / "agents" / "segment_proposer.json").read_text(
            encoding="utf-8"
        )
    )
    (analysis_root / "segment-proposal.json").write_text(
        json.dumps(proposal, ensure_ascii=False),
        encoding="utf-8",
    )
    checkpoint = AnalysisCheckpoint(sampleId="sample-1")
    checkpoint.mark_stage_complete("proposing_segments")
    checkpoint.save(analysis_root / "checkpoint.json")

    context = TaskContext(project_id="project-1", task_id="task-1", storage_root=tmp_path)
    structure = run_structure_analysis_pipeline(
        runner,
        analysis=_sample_analysis(),
        context=context,
        project_id="project-1",
        source_video_id="sample-1",
        analysis_root=analysis_root,
        resume=True,
        checkpoint=checkpoint,
        checkpoint_path=analysis_root / "checkpoint.json",
    )

    assert structure.get("version") == "p1-v3"
    assert (analysis_root / "segment-analyses.json").is_file()
    quality = structure.get("analysisQuality") or {}
    assert isinstance(quality.get("warnings"), list)


def test_structure_pipeline_records_critic_skip_warning(tmp_path: Path, monkeypatch) -> None:
    fixtures = load_agent_fixtures(Path(__file__).parent / "fixtures" / "agents")
    runner = AgentRunner(
        llm=LLMTool(fixture_mode=True, fixtures=fixtures),
        prompt_loader=PromptLoader(),
        observability_sink=build_observability_sink(tmp_path),
        model_name="fixture",
    )

    def _boom(*args, **kwargs):
        raise RuntimeError("critic unavailable")

    monkeypatch.setattr(
        "app.pipelines.structure_analysis_pipeline.run_structure_critic",
        _boom,
    )

    analysis_root = tmp_path / "analysis"
    analysis_root.mkdir(parents=True)
    context = TaskContext(project_id="project-1", task_id="task-1", storage_root=tmp_path)
    structure = run_structure_analysis_pipeline(
        runner,
        analysis=_sample_analysis(),
        context=context,
        project_id="project-1",
        source_video_id="sample-1",
        analysis_root=analysis_root,
    )

    warnings = list((structure.get("analysisQuality") or {}).get("warnings") or [])
    assert any(str(item).startswith("critic_skipped:") for item in warnings)


def test_structure_pipeline_records_segment_vision_skip_warnings(tmp_path: Path) -> None:
    fixtures = load_agent_fixtures(Path(__file__).parent / "fixtures" / "agents")
    runner = AgentRunner(
        llm=LLMTool(fixture_mode=True, fixtures=fixtures),
        prompt_loader=PromptLoader(),
        observability_sink=build_observability_sink(tmp_path),
        model_name="fixture",
    )
    analysis = _sample_analysis()
    analysis["keyframeBatchDigests"] = [
        {
            "batchIndex": 0,
            "startSec": 0.0,
            "endSec": 999.0,
            "frames": [],
            "visualFacts": "full coverage",
            "onScreenTextFacts": [],
        }
    ]
    analysis["analysisDepth"] = "standard"

    analysis_root = tmp_path / "analysis"
    analysis_root.mkdir(parents=True)
    context = TaskContext(project_id="project-1", task_id="task-1", storage_root=tmp_path)
    structure = run_structure_analysis_pipeline(
        runner,
        analysis=analysis,
        context=context,
        project_id="project-1",
        source_video_id="sample-1",
        analysis_root=analysis_root,
    )

    warnings = list((structure.get("analysisQuality") or {}).get("warnings") or [])
    assert any("vision_skipped_digest_coverage" in str(item) for item in warnings)
