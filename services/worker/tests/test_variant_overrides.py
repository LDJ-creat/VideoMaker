from __future__ import annotations

import json
from pathlib import Path

from app.agents.gap_planner import apply_provider_selection, reconcile_gap_buckets
from app.agents.slot_mapper import post_validate_slot_matches
from app.config.variants import clear_registry_cache, load_variant_gap_planner_overrides
from app.pipelines.gap_selection import select_provider
from app.runtime.video_gen_quota import VideoGenQuota


def _fixtures_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "agents"


def _load_structure_fixture() -> dict:
    path = Path(__file__).parent / "fixtures" / "structures" / "sample-structure.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _inventory() -> dict:
    return {
        "id": "inventory-project-1",
        "projectId": "project-1",
        "userBrief": {"topic": "demo", "sellingPoints": ["便携"]},
        "assets": [],
        "extractedFacts": [],
        "candidateMoments": [],
    }


def _missing_visual_slot() -> dict:
    return {
        "id": "seg-hook-hook_visual-1",
        "segmentId": "seg-hook",
        "role": "hook_visual",
        "importance": "must_have",
        "requiredAssetType": ["video", "image"],
    }


def test_variant_registry_gap_planner_overrides_differ() -> None:
    clear_registry_cache()
    high_click = load_variant_gap_planner_overrides("high_click")
    high_conversion = load_variant_gap_planner_overrides("high_conversion")
    assert high_click["videoGenPriority"] == "high"
    assert high_conversion["videoGenPriority"] == "low"
    assert high_click["preferProviders"][0] == "hyperframes_material"
    assert high_conversion["preferProviders"][-1] == "image_generation"


def test_high_click_prefers_video_generation_when_quota_available() -> None:
    slot = _missing_visual_slot()
    overrides = load_variant_gap_planner_overrides("high_click")
    provider = select_provider(
        slot,
        weak_match=None,
        quota=VideoGenQuota(max_calls=1),
        variant_overrides=overrides,
        impact="high",
    )
    assert provider == "video_generation"


def test_high_conversion_prefers_image_generation_over_video() -> None:
    slot = _missing_visual_slot()
    overrides = load_variant_gap_planner_overrides("high_conversion")
    provider = select_provider(
        slot,
        weak_match=None,
        quota=VideoGenQuota(max_calls=1),
        variant_overrides=overrides,
        impact="high",
    )
    assert provider == "image_generation"


def test_apply_provider_selection_uses_variant_specific_chain() -> None:
    structure = _load_structure_fixture()
    inventory = _inventory()
    slot_matches = post_validate_slot_matches(
        json.loads((_fixtures_dir() / "slot_mapper.json").read_text(encoding="utf-8"))["slotMatches"],
        structure=structure,
        inventory=inventory,
    )
    gap_report = json.loads((_fixtures_dir() / "gap_planner.json").read_text(encoding="utf-8"))
    gap_report = reconcile_gap_buckets(
        gap_report,
        structure=structure,
        slot_matches=slot_matches,
    )
    gap_report["slotMatches"] = slot_matches

    high_click = apply_provider_selection(
        dict(gap_report),
        structure=structure,
        slot_matches=slot_matches,
        quota=VideoGenQuota(max_calls=1),
        variant_overrides=load_variant_gap_planner_overrides("high_click"),
    )
    high_conversion = apply_provider_selection(
        dict(gap_report),
        structure=structure,
        slot_matches=slot_matches,
        quota=VideoGenQuota(max_calls=1),
        variant_overrides=load_variant_gap_planner_overrides("high_conversion"),
    )

    click_missing = next(
        item for item in high_click["missingSlots"] if item["slotId"] == "seg-hook-hook_visual-1"
    )
    conversion_missing = next(
        item
        for item in high_conversion["missingSlots"]
        if item["slotId"] == "seg-hook-hook_visual-1"
    )
    assert click_missing["suggestedFixes"][0] == "video_generation"
    assert conversion_missing["suggestedFixes"][0] == "image_generation"


def test_each_generation_gets_fresh_video_gen_quota() -> None:
    first = VideoGenQuota(max_calls=1)
    second = VideoGenQuota(max_calls=1)
    assert first.consume()
    assert not first.has_video_quota()
    assert second.has_video_quota()


def test_run_agent_generation_sets_variant_on_plan(tmp_path: Path) -> None:
    from app.agents.prompt_loader import PromptLoader
    from app.agents.runner import AgentRunner
    from app.pipelines.generation_pipeline import run_agent_generation
    from app.observability.sink import LocalFileSink
    from app.runtime.agent_run_store import AgentRunStore
    from app.runtime.task_context import TaskContext
    from app.tools.llm_tool import LLMTool, load_agent_fixtures

    fixtures_dir = Path(__file__).parent / "fixtures" / "agents"
    runner = AgentRunner(
        llm=LLMTool(fixture_mode=True, fixtures=load_agent_fixtures(fixtures_dir)),
        prompt_loader=PromptLoader(),
        observability_sink=LocalFileSink(AgentRunStore(tmp_path)),
    )
    context = TaskContext(project_id="project-1", task_id="task-1", storage_root=tmp_path)
    structure = json.loads(
        (Path(__file__).parent / "fixtures" / "structures" / "sample-structure.json").read_text(
            encoding="utf-8",
        )
    )
    inventory = {
        "id": "inventory-project-1",
        "projectId": "project-1",
        "userBrief": {"sellingPoints": ["便携"]},
        "assets": [],
        "extractedFacts": [],
        "candidateMoments": [],
    }

    _, _, gap_click, plan_click = run_agent_generation(
        runner,
        structure=structure,
        inventory=inventory,
        context=context,
        generation_id="gen-click",
        variant="high_click",
    )
    _, _, gap_conv, plan_conv = run_agent_generation(
        runner,
        structure=structure,
        inventory=inventory,
        context=context,
        generation_id="gen-conv",
        variant="high_conversion",
    )

    assert plan_click["variant"] == "high_click"
    assert plan_conv["variant"] == "high_conversion"
    click_missing = gap_click["missingSlots"][0]["suggestedFixes"][0]
    conv_missing = gap_conv["missingSlots"][0]["suggestedFixes"][0]
    assert click_missing == "video_generation"
    assert conv_missing == "image_generation"
