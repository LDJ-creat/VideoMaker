from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.pipelines.p0_demo_pipeline import P0DemoPipeline
from app.tools.llm_tool import LLMTool, load_agent_fixtures


class _RecordingPipeline(P0DemoPipeline):
    def __init__(self, storage_root: Path, sample_result: dict[str, Any], structure: dict[str, Any]) -> None:
        fixtures = load_agent_fixtures(Path(__file__).parent / "fixtures" / "agents")
        super().__init__(
            storage_root,
            llm=LLMTool(fixture_mode=True, fixtures=fixtures),
        )
        self._sample_result = sample_result
        self._structure = structure

    def analyze_sample(self, **kwargs: Any) -> dict[str, Any]:
        emit = kwargs["emit"]
        project_id = kwargs["project_id"]
        sample_id = kwargs["sample_id"]
        analysis_dir = self._storage_root / "projects" / project_id / "samples" / sample_id / "analysis"
        analysis_dir.mkdir(parents=True, exist_ok=True)
        (analysis_dir / "sample-analysis.json").write_text(
            json.dumps(self._sample_result),
            encoding="utf-8",
        )
        emit(status="running", stage="extracting_structure", progress=90, message="structure")
        emit(status="succeeded", stage="completed", progress=100, message="done")
        return {"ok": True, "structure": self._structure}


class _StubSamplePipeline:
    def __init__(self, storage_root: Path) -> None:
        self._storage_root = storage_root
        self.last_kwargs: dict[str, Any] = {}

    def run(self, project_id: str, sample_id: str, task_id: str, **kwargs: Any) -> dict[str, Any]:
        self.last_kwargs = dict(kwargs)
        analysis_dir = (
            self._storage_root / "projects" / project_id / "samples" / sample_id / "analysis"
        )
        analysis_dir.mkdir(parents=True, exist_ok=True)
        if not (analysis_dir / "sample-analysis.json").is_file():
            fixture_path = Path(__file__).parent / "fixtures" / "sample_analysis.json"
            (analysis_dir / "sample-analysis.json").write_text(
                fixture_path.read_text(encoding="utf-8"),
                encoding="utf-8",
            )
        checkpoint_path = analysis_dir / "checkpoint.json"
        checkpoint_path.write_text(
            json.dumps({"sampleId": sample_id, "completedStages": ["consolidating"]}),
            encoding="utf-8",
        )
        return {
            "finalEvent": {"status": "succeeded", "stage": "completed", "progress": 100},
            "artifactRefs": [],
        }


class _DirectRoutePipeline(P0DemoPipeline):
    def _resolve_structure_analysis_route(self) -> str:
        return "direct_multimodal"


def _load_structure_fixture() -> dict[str, Any]:
    fixture_path = Path(__file__).parent / "fixtures" / "structures" / "sample-structure.json"
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def test_p0_demo_pipeline_fixture_e2e_dual_variant_and_revise_without_hf_cli(
    tmp_path: Path,
) -> None:
    """Full fixture-mode generation + revise must not require live HyperFrames CLI."""
    fixture_path = Path(__file__).parent / "fixtures" / "sample_analysis.json"
    sample_analysis = json.loads(fixture_path.read_text(encoding="utf-8"))
    structure = _load_structure_fixture()
    fixtures = load_agent_fixtures(Path(__file__).parent / "fixtures" / "agents")

    pipeline = _RecordingPipeline(tmp_path, sample_analysis, structure)
    events: list[dict[str, Any]] = []

    def emit(**kwargs: Any) -> dict[str, Any]:
        events.append(kwargs)
        return kwargs

    for variant in ("high_click", "high_conversion"):
        result = pipeline.run_generation(
            project_id="project-1",
            task_id=f"task-{variant}",
            generation_id=f"gen-{variant}",
            structure=structure,
            user_brief={
                "topic": "果汁机",
                "sellingPoints": ["便携"],
                "mustMention": [],
                "avoidMention": [],
            },
            assets=[
                {
                    "id": "asset-1",
                    "type": "text",
                    "uri": "storage://caption.txt",
                    "description": "caption",
                    "tags": ["卖点"],
                }
            ],
            emit=emit,
            variant=variant,
        )
        assert result["ok"] is True
        assert result["plan"]["variant"] == variant
        assert result["gapReport"]["projectId"] == "project-1"
        assert result["plan"]["timeline"]["tracks"]

    revise = pipeline.run_revise(
        project_id="project-1",
        task_id="task-revise",
        source_generation_id="gen-high_click",
        generation_id="gen-revised",
        instruction="开头更抓人，字幕少一点",
        structure=structure,
        user_brief={
            "topic": "果汁机",
            "sellingPoints": ["便携"],
            "mustMention": [],
            "avoidMention": [],
        },
        assets=[
            {
                "id": "asset-1",
                "type": "text",
                "uri": "storage://caption.txt",
                "description": "caption",
                "tags": ["卖点"],
            }
        ],
        emit=emit,
    )
    assert revise["ok"] is True
    assert len(revise.get("intents", [])) >= 1
    stages = [event["stage"] for event in events]
    assert "parsing_edit_intent" in stages
    assert "generating_material" in stages
    assert events[-1]["status"] == "succeeded"


def test_run_generation_fails_when_agent_fixture_invalid(tmp_path: Path) -> None:
    structure = _load_structure_fixture()
    fixtures = load_agent_fixtures(Path(__file__).parent / "fixtures" / "agents")
    fixtures["slot_mapper"] = {"slotMatches": [{"slotId": "incomplete"}]}

    pipeline = P0DemoPipeline(tmp_path, llm=LLMTool(fixture_mode=True, fixtures=fixtures))
    events: list[dict[str, Any]] = []

    def emit(**kwargs: Any) -> dict[str, Any]:
        events.append(kwargs)
        return kwargs

    result = pipeline.run_generation(
        project_id="project-1",
        task_id="task-gen",
        generation_id="gen-1",
        structure=structure,
        user_brief={"topic": "果汁机", "sellingPoints": ["便携"], "mustMention": [], "avoidMention": []},
        assets=[
            {
                "id": "asset-1",
                "type": "text",
                "uri": "storage://caption.txt",
                "description": "caption",
                "tags": ["卖点"],
            }
        ],
        emit=emit,
    )

    assert result["ok"] is False
    assert events[-1]["status"] == "failed"
    assert events[-1]["stage"] == "mapping_slots"
    assert events[-1]["error"]["code"] == "agent_failed"


def test_analyze_sample_fails_when_structure_agent_invalid(tmp_path: Path) -> None:
    fixtures = load_agent_fixtures(Path(__file__).parent / "fixtures" / "agents")
    fixtures["segment_proposer"] = {"segments": [{"id": "bad-only"}]}
    pipeline = P0DemoPipeline(
        tmp_path,
        llm=LLMTool(fixture_mode=True, fixtures=fixtures),
    )
    pipeline._sample_pipeline = _StubSamplePipeline(tmp_path)  # noqa: SLF001
    events: list[dict[str, Any]] = []

    def emit(**kwargs: Any) -> dict[str, Any]:
        events.append(kwargs)
        return kwargs

    result = pipeline.analyze_sample(
        project_id="project-1",
        task_id="task-analyze",
        sample_id="sample-1",
        emit=emit,
    )

    assert result["ok"] is False
    assert events[-1]["status"] == "failed"
    assert events[-1]["stage"] == "extracting_structure"
    assert events[-1]["error"]["code"] in {"agent_failed", "LLMValidationError"}


def test_analyze_sample_passes_skip_keyframes_for_direct_route(tmp_path: Path) -> None:
    fixtures = load_agent_fixtures(Path(__file__).parent / "fixtures" / "agents")
    stub = _StubSamplePipeline(tmp_path)
    pipeline = _DirectRoutePipeline(
        tmp_path,
        llm=LLMTool(fixture_mode=True, fixtures=fixtures),
    )
    pipeline._sample_pipeline = stub  # noqa: SLF001
    events: list[dict[str, Any]] = []

    def emit(**kwargs: Any) -> dict[str, Any]:
        events.append(kwargs)
        return kwargs

    sample_root = tmp_path / "projects" / "project-1" / "samples" / "sample-1"
    sample_root.mkdir(parents=True, exist_ok=True)
    (sample_root / "source.mp4").write_bytes(b"video")

    result = pipeline.analyze_sample(
        project_id="project-1",
        task_id="task-analyze-direct",
        sample_id="sample-1",
        video_path=sample_root / "source.mp4",
        emit=emit,
    )

    assert stub.last_kwargs.get("skip_keyframe_extraction") is True
    assert result["ok"] is True
    checkpoint = json.loads(
        (
            tmp_path
            / "projects"
            / "project-1"
            / "samples"
            / "sample-1"
            / "analysis"
            / "checkpoint.json"
        ).read_text(encoding="utf-8")
    )
    assert checkpoint.get("analysisRoute") == "direct_multimodal"
