from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.agents.runner import AgentRunner
from app.agents.prompt_loader import PromptLoader
from app.observability.sink import build_observability_sink
from app.pipelines.direct_video_structure_pipeline import run_direct_video_structure_pipeline
from app.runtime.checkpoint import AnalysisCheckpoint
from app.runtime.task_context import TaskContext
from app.tools.llm_tool import LLMTool, load_agent_fixtures


@pytest.fixture()
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures" / "agents"


def test_direct_video_structure_pipeline_fixture_mode(tmp_path: Path, fixtures_dir: Path) -> None:
    analysis_root = tmp_path / "analysis"
    analysis_root.mkdir(parents=True)
    video_path = tmp_path / "sample.mp4"
    video_path.write_bytes(b"\x00\x00\x00\x18ftypmp42")

    analysis = {
        "metadata": {"durationSec": 30.0, "hasAudio": True},
        "transcript": {"segments": [{"startSec": 0, "endSec": 1, "text": "hello"}]},
        "shots": [
            {"id": f"s{i}", "startSec": start, "endSec": end}
            for i, (start, end) in enumerate(
                [
                    (0.0, 1.0),
                    (1.0, 2.1),
                    (2.1, 3.0),
                    (3.0, 5.0),
                    (5.0, 8.4),
                    (8.4, 14.0),
                    (14.0, 22.0),
                    (22.0, 30.0),
                ]
            )
        ],
        "keyframes": [],
        "locale": "zh",
        "structureAnalysisRoute": "direct_multimodal",
    }
    (analysis_root / "sample-analysis.json").write_text(
        json.dumps(analysis, ensure_ascii=False),
        encoding="utf-8",
    )

    runner = AgentRunner(
        llm=LLMTool(
            fixture_mode=True,
            fixtures=load_agent_fixtures(fixtures_dir),
        ),
        prompt_loader=PromptLoader(),
        observability_sink=build_observability_sink(tmp_path),
        model_name="fixture",
    )
    context = TaskContext(project_id="project-1", task_id="task-1", storage_root=tmp_path)
    checkpoint = AnalysisCheckpoint(sampleId="sample-1", analysisRoute="direct_multimodal")
    checkpoint_path = analysis_root / "checkpoint.json"

    structure = run_direct_video_structure_pipeline(
        runner,
        analysis=analysis,
        video_path=video_path,
        analysis_root=analysis_root,
        context=context,
        project_id="project-1",
        source_video_id="sample-1",
        checkpoint=checkpoint,
        checkpoint_path=checkpoint_path,
    )

    assert structure["projectId"] == "project-1"
    assert len(structure["rhythm"]["shotBoundaries"]) == len(analysis["shots"])
    assert structure["rhythm"]["shotBoundaries"][0]["startSec"] == analysis["shots"][0]["startSec"]
    saved = json.loads((analysis_root / "sample-analysis.json").read_text(encoding="utf-8"))
    assert saved["structureAnalysisRoute"] == "direct_multimodal"
    warnings = list((structure.get("analysisQuality") or {}).get("warnings") or [])
    assert "analysis_route:direct_multimodal" in warnings
    assert "extracting_structure_direct" in checkpoint.completedStages
