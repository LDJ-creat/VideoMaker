from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.agents.prompt_loader import PromptLoader
from app.agents.runner import AgentRunner
from app.pipelines.asset_understanding import (
    compute_highlight_score,
    moment_id,
    normalize_score,
    run_asset_understanding,
    score_shot_moment,
)
from app.pipelines.generation_pipeline import build_asset_inventory, run_agent_generation
from app.observability.sink import LocalFileSink
from app.runtime.agent_run_store import AgentRunStore
from app.runtime.task_context import TaskContext
from app.tools.llm_tool import LLMTool, load_agent_fixtures
from app.validation.schema_loader import validate_contract


def _fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures" / "agents"


def _load_structure_fixture() -> dict[str, Any]:
    fixture_path = Path(__file__).parent / "fixtures" / "structures" / "sample-structure.json"
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def test_compute_highlight_score_formula() -> None:
    score = compute_highlight_score(motion_score=1.0, sharpness_score=0.0, center_subject_score=0.0)
    assert score == pytest.approx(0.4)
    score = compute_highlight_score(motion_score=0.0, sharpness_score=1.0, center_subject_score=0.0)
    assert score == pytest.approx(0.3)
    score = compute_highlight_score(motion_score=0.0, sharpness_score=0.0, center_subject_score=1.0)
    assert score == pytest.approx(0.3)


def test_moment_id_is_stable_from_time_range() -> None:
    assert moment_id("asset-1", 0.0, 1.5) == "moment-asset-1-0-1500"


def test_normalize_score_clamps_and_scales() -> None:
    assert normalize_score(5.0, 0.0, 10.0) == pytest.approx(0.5)
    assert normalize_score(0.0, 0.0, 0.0) == 1.0
    assert normalize_score(-1.0, 0.0, 1.0) == 0.0
    assert normalize_score(2.0, 0.0, 1.0) == 1.0


def test_score_shot_moment_uses_frame_metrics_when_present() -> None:
    score = score_shot_moment(
        {"confidence": 0.2},
        frame_metrics={"motionScore": 1.0, "sharpnessScore": 1.0, "centerSubjectScore": 1.0},
    )
    assert score == pytest.approx(1.0)


def test_score_shot_moment_falls_back_to_shot_confidence() -> None:
    score = score_shot_moment({"confidence": 0.8})
    assert 0.0 <= score <= 1.0
    assert score > score_shot_moment({"confidence": 0.2})


def test_run_asset_understanding_enriches_video_moments(tmp_path: Path) -> None:
    project_id = "project-1"
    asset_id = "asset-video-1"
    analysis_dir = tmp_path / "projects" / project_id / "assets" / asset_id / "analysis"
    analysis_dir.mkdir(parents=True)
    (analysis_dir / "shots.json").write_text(
        json.dumps(
            [
                {"startSec": 0.0, "endSec": 1.5, "confidence": 0.9, "changeReason": "visual_cut"},
                {"startSec": 1.5, "endSec": 3.0, "confidence": 0.6, "changeReason": "scene_change"},
            ]
        ),
        encoding="utf-8",
    )
    (analysis_dir / "asset-analysis.json").write_text(
        json.dumps(
            {
                "transcript": [
                    {"startSec": 0.0, "endSec": 1.5, "text": "开场展示产品"},
                ]
            }
        ),
        encoding="utf-8",
    )

    fixtures = load_agent_fixtures(_fixtures_dir())
    runner = AgentRunner(
        llm=LLMTool(fixture_mode=True, fixtures=fixtures),
        prompt_loader=PromptLoader(),
        observability_sink=LocalFileSink(AgentRunStore(tmp_path)),
    )
    context = TaskContext(project_id=project_id, task_id="task-1", storage_root=tmp_path)

    baseline = build_asset_inventory(
        project_id=project_id,
        user_brief={
            "topic": "便携果汁机",
            "productName": "JuiceGo",
            "sellingPoints": ["便携", "快"],
            "mustMention": [],
            "avoidMention": [],
        },
        assets=[
            {
                "id": asset_id,
                "type": "video",
                "uri": str(tmp_path / "missing-video.mp4"),
                "description": "产品演示",
                "tags": ["demo"],
                "durationSec": 3.0,
            }
        ],
    )

    inventory = run_asset_understanding(
        runner,
        inventory=baseline,
        context=context,
        generation_id="gen-1",
    )

    validation = validate_contract("asset-inventory", inventory)
    assert validation.valid, validation.errors
    assert inventory["extractedFacts"]
    assert len(inventory["candidateMoments"]) >= 1

    top_moment = max(inventory["candidateMoments"], key=lambda item: item.get("highlightScore", 0))
    assert top_moment.get("highlightScore") is not None
    assert top_moment.get("visualTags")
    assert top_moment.get("suggestedSegmentRoles")
    assert top_moment["id"] == moment_id(asset_id, 0.0, 1.5)
    assert inventory["assets"][0]["tags"] == ["demo", "product", "close-up"]
    assert any(event["stage"] == "analyzing_assets" for event in context.emitted_events)


def test_run_asset_understanding_picks_global_top_moments_across_assets(tmp_path: Path) -> None:
    project_id = "project-1"
    fixtures = load_agent_fixtures(_fixtures_dir())
    fixtures["asset_moment_vision"] = {
        "analyses": [
            {
                "momentId": moment_id("asset-low", 0.0, 1.0),
                "visualTags": ["b-roll"],
                "suggestedSegmentRoles": ["mid"],
                "description": "low score",
            },
            {
                "momentId": moment_id("asset-high", 0.0, 1.0),
                "visualTags": ["hero"],
                "suggestedSegmentRoles": ["hook"],
                "description": "high score",
            },
        ]
    }

    for asset_id, confidence in (("asset-low", 0.3), ("asset-high", 0.95)):
        analysis_dir = tmp_path / "projects" / project_id / "assets" / asset_id / "analysis"
        analysis_dir.mkdir(parents=True)
        (analysis_dir / "shots.json").write_text(
            json.dumps([{"startSec": 0.0, "endSec": 1.0, "confidence": confidence}]),
            encoding="utf-8",
        )

    runner = AgentRunner(
        llm=LLMTool(fixture_mode=True, fixtures=fixtures),
        prompt_loader=PromptLoader(),
        observability_sink=LocalFileSink(AgentRunStore(tmp_path)),
    )
    context = TaskContext(project_id=project_id, task_id="task-1", storage_root=tmp_path)
    baseline = build_asset_inventory(
        project_id=project_id,
        user_brief={"topic": "x", "sellingPoints": ["a"], "mustMention": [], "avoidMention": []},
        assets=[
            {
                "id": "asset-low",
                "type": "video",
                "uri": "storage://missing-low.mp4",
                "durationSec": 1.0,
            },
            {
                "id": "asset-high",
                "type": "video",
                "uri": "storage://missing-high.mp4",
                "durationSec": 1.0,
            },
        ],
    )

    inventory = run_asset_understanding(
        runner,
        inventory=baseline,
        context=context,
        generation_id="gen-1",
    )

    enriched = next(
        moment for moment in inventory["candidateMoments"] if moment["assetId"] == "asset-high"
    )
    assert enriched.get("visualTags") == ["hero"]


def test_run_asset_understanding_adds_image_moment(tmp_path: Path) -> None:
    fixtures = load_agent_fixtures(_fixtures_dir())
    fixtures["asset_moment_vision"] = {
        "analyses": [
            {
                "momentId": moment_id("asset-image-1", 0.0, 0.1),
                "visualTags": ["packshot"],
                "suggestedSegmentRoles": ["cta"],
                "description": "产品包装图",
            }
        ]
    }

    runner = AgentRunner(
        llm=LLMTool(fixture_mode=True, fixtures=fixtures),
        prompt_loader=PromptLoader(),
        observability_sink=LocalFileSink(AgentRunStore(tmp_path)),
    )
    context = TaskContext(project_id="project-1", task_id="task-1", storage_root=tmp_path)
    baseline = build_asset_inventory(
        project_id="project-1",
        user_brief={"topic": "x", "sellingPoints": ["a"], "mustMention": [], "avoidMention": []},
        assets=[
            {
                "id": "asset-image-1",
                "type": "image",
                "uri": "storage://image.jpg",
                "description": "包装图",
                "tags": [],
            }
        ],
    )

    inventory = run_asset_understanding(
        runner,
        inventory=baseline,
        context=context,
        generation_id="gen-1",
    )

    assert len(inventory["candidateMoments"]) == 1
    assert inventory["candidateMoments"][0]["visualTags"] == ["packshot"]
    assert inventory["assets"][0]["tags"] == ["packshot"]


def test_run_asset_understanding_respects_avoid_mention_in_facts(tmp_path: Path) -> None:
    fixtures = load_agent_fixtures(_fixtures_dir())
    fixtures["content_strategist"] = {
        "extractedFacts": [
            {
                "id": "fact-bad",
                "kind": "selling_point",
                "text": "竞品品牌X更好",
                "source": "agent",
            }
        ],
        "toneSummary": "direct",
    }

    runner = AgentRunner(
        llm=LLMTool(fixture_mode=True, fixtures=fixtures),
        prompt_loader=PromptLoader(),
        observability_sink=LocalFileSink(AgentRunStore(tmp_path)),
    )
    context = TaskContext(project_id="project-1", task_id="task-1", storage_root=tmp_path)
    baseline = build_asset_inventory(
        project_id="project-1",
        user_brief={
            "topic": "果汁机",
            "sellingPoints": ["便携"],
            "mustMention": [],
            "avoidMention": ["竞品品牌X"],
        },
        assets=[
            {
                "id": "asset-text-1",
                "type": "text",
                "uri": "storage://caption.txt",
                "description": "caption",
                "tags": [],
            }
        ],
    )

    inventory = run_asset_understanding(
        runner,
        inventory=baseline,
        context=context,
        generation_id="gen-1",
    )

    assert not any(fact.get("id") == "fact-bad" for fact in inventory["extractedFacts"])
    agent_facts = [
        fact for fact in inventory["extractedFacts"] if str(fact.get("source", "")).startswith("agent")
    ]
    assert all("竞品品牌X" not in fact["text"] for fact in agent_facts)


def test_run_agent_generation_accepts_pre_enriched_inventory(tmp_path: Path) -> None:
    structure = _load_structure_fixture()
    fixtures = load_agent_fixtures(_fixtures_dir())
    runner = AgentRunner(
        llm=LLMTool(fixture_mode=True, fixtures=fixtures),
        prompt_loader=PromptLoader(),
        observability_sink=LocalFileSink(AgentRunStore(tmp_path)),
    )
    context = TaskContext(project_id="project-1", task_id="task-1", storage_root=tmp_path)

    inventory = run_asset_understanding(
        runner,
        inventory=build_asset_inventory(
            project_id="project-1",
            user_brief={"topic": "x", "sellingPoints": ["便携"], "mustMention": [], "avoidMention": []},
            assets=[
                {
                    "id": "asset-text-1",
                    "type": "text",
                    "uri": "storage://caption.txt",
                    "description": "caption",
                    "tags": [],
                }
            ],
        ),
        context=context,
        generation_id="gen-1",
    )

    _, slot_matches, gap_report, plan = run_agent_generation(
        runner,
        structure=structure,
        inventory=inventory,
        context=context,
        generation_id="gen-1",
    )

    assert slot_matches
    assert gap_report["projectId"] == "project-1"
    assert plan["timeline"]["tracks"]
