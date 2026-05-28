from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.pipelines.p0_demo_pipeline import P0DemoPipeline


class _RecordingPipeline(P0DemoPipeline):
    def __init__(self, storage_root: Path, sample_result: dict[str, Any], structure: dict[str, Any]) -> None:
        super().__init__(storage_root)
        self._sample_result = sample_result
        self._structure = structure

    def analyze_sample(self, **kwargs: Any) -> dict[str, Any]:
        emit = kwargs["emit"]
        project_id = kwargs["project_id"]
        task_id = kwargs["task_id"]
        analysis_dir = self._storage_root / "projects" / project_id / "samples" / task_id
        analysis_dir.mkdir(parents=True, exist_ok=True)
        (analysis_dir / "sample-analysis.json").write_text(
            json.dumps(self._sample_result),
            encoding="utf-8",
        )
        emit(status="running", stage="extracting_structure", progress=90, message="structure")
        emit(status="succeeded", stage="completed", progress=100, message="done")
        return {"ok": True, "structure": self._structure}


def test_p0_demo_pipeline_generation_uses_fixture_structure(tmp_path: Path) -> None:
    fixture_path = Path(__file__).parent / "fixtures" / "sample_analysis.json"
    sample_analysis = json.loads(fixture_path.read_text(encoding="utf-8"))
    from app.pipelines.structure_pipeline import extract_video_structure

    structure = extract_video_structure(
        sample_analysis=sample_analysis,
        project_id="project-1",
        source_video_id="sample-1",
    )

    pipeline = _RecordingPipeline(tmp_path, sample_analysis, structure)
    events: list[dict[str, Any]] = []

    def emit(**kwargs: Any) -> dict[str, Any]:
        events.append(kwargs)
        return kwargs

    result = pipeline.run_generation(
        project_id="project-1",
        task_id="task-gen",
        generation_id="gen-1",
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

    assert result["ok"] is True
    assert result["gapReport"]["projectId"] == "project-1"
    assert result["plan"]["timeline"]["tracks"]
    assert events[-1]["status"] == "succeeded"
