from __future__ import annotations

from typing import Any

from app.pipelines.p0_demo_pipeline import P0DemoPipeline
from app.tools.llm_tool import LLMTool


class _FailAllAgentsPipeline(P0DemoPipeline):
    def __init__(self, storage_root) -> None:  # noqa: ANN001
        super().__init__(storage_root, llm=LLMTool(fixture_mode=True, fixtures={}))

    def _build_runner(self):  # noqa: ANN001
        class _Runner:
            class _Llm:
                def generate_json(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
                    raise RuntimeError("llm unavailable")

            llm = _Llm()

            def run(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
                raise RuntimeError("agent unavailable")

        return _Runner()


def test_run_plan_revise_returns_structured_failure_without_task_events(
    tmp_path,
) -> None:
    pipeline = _FailAllAgentsPipeline(tmp_path)
    result = pipeline.run_plan_revise(
        project_id="project-1",
        task_id="plan-revise",
        generation_id="gen-1",
        instruction="把背景音乐换成更轻快的",
        source_plan={
            "variant": "high_click",
            "storyboard": [],
            "timeline": {"durationSec": 10.0, "tracks": []},
            "packagingPlan": {"subtitle": {"density": "medium"}},
        },
        session=None,
        emit=lambda **kwargs: kwargs,
    )
    assert result["ok"] is False
    assert result["finalEvent"]["status"] == "failed"
    assert "Could not parse any edit intents from instruction" in str(result["error"])


def test_run_plan_revise_rule_fallback_still_works(tmp_path) -> None:
    pipeline = _FailAllAgentsPipeline(tmp_path)
    result = pipeline.run_plan_revise(
        project_id="project-1",
        task_id="plan-revise",
        generation_id="gen-1",
        instruction="字幕少一点",
        source_plan={
            "variant": "high_click",
            "storyboard": [],
            "timeline": {"durationSec": 10.0, "tracks": []},
            "packagingPlan": {"subtitle": {"density": "medium"}},
        },
        session=None,
        emit=lambda **kwargs: kwargs,
    )
    assert result["ok"] is True
    assert result["plannerOutput"]["executionMode"] == "in_place"
