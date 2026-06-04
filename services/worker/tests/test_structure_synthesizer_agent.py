from __future__ import annotations

import copy
from pathlib import Path

import pytest

from app.agents.prompt_loader import PromptLoader
from app.agents.runner import AgentRunner
from app.agents.structure_synthesizer import run_structure_synthesizer
from app.observability.sink import LocalFileSink
from app.runtime.agent_run_store import AgentRunStore
from app.runtime.task_context import TaskContext
from app.tools.llm_tool import LLMTool, load_agent_fixtures


def _primary_structure(project_id: str, sample_id: str) -> dict:
    return {
        "id": f"video-structure-{sample_id}",
        "projectId": project_id,
        "sourceVideoId": sample_id,
        "version": "p0-v1",
        "metadata": {"durationSec": 30.0},
        "narrative": {
            "summary": "primary",
            "segments": [
                {
                    "id": "seg-hook",
                    "role": "hook",
                    "startSec": 0.0,
                    "endSec": 3.0,
                    "scriptSummary": "hook",
                    "visualSummary": "hook",
                    "intent": "hook",
                }
            ],
        },
        "rhythm": {
            "totalDurationSec": 30.0,
            "shotCount": 4,
            "avgShotDurationSec": 7.5,
            "tempo": "fast",
            "beatPoints": [],
            "shotBoundaries": [],
        },
        "packaging": {
            "titleCards": [],
            "stickers": [],
            "transitions": [],
            "visualDensity": "medium",
        },
        "slots": [
            {
                "id": "slot-hook",
                "segmentId": "seg-hook",
                "role": "hook",
                "startSec": 0.0,
                "endSec": 3.0,
                "requiredAssetType": "video",
                "visualIntent": "hook",
                "scriptIntent": "hook",
                "importance": "required",
                "constraints": {},
            }
        ],
        "evidence": [],
        "confidence": 0.8,
    }


def test_run_structure_synthesizer_fixture_fallback(tmp_path: Path) -> None:
    fixtures_dir = Path(__file__).parent / "fixtures" / "agents"
    runner = AgentRunner(
        llm=LLMTool(fixture_mode=True, fixtures=load_agent_fixtures(fixtures_dir)),
        prompt_loader=PromptLoader(),
        observability_sink=LocalFileSink(AgentRunStore(tmp_path)),
    )
    context = TaskContext(project_id="project-1", task_id="task-1", storage_root=tmp_path)
    primary = _primary_structure("project-1", "sample-primary")
    reference = copy.deepcopy(primary)
    reference["id"] = "video-structure-ref"
    reference["sourceVideoId"] = "sample-ref"

    structure, provenance = run_structure_synthesizer(
        runner,
        context=context,
        project_id="project-1",
        generation_run_id="run-1",
        primary_sample_id="sample-primary",
        primary_structure=primary,
        reference_structures=[reference],
        reference_sample_ids=["sample-ref"],
        user_brief={"topic": "demo"},
    )

    assert structure["sourceVideoId"] == "sample-primary"
    assert structure["id"] == "synthesized-run-1"
    assert provenance["primarySampleId"] == "sample-primary"
    assert provenance["referenceSampleIds"] == ["sample-ref"]
