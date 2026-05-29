from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.agents.gap_planner import apply_provider_selection, reconcile_gap_buckets, run_gap_planner
from app.config.variants import clear_registry_cache, load_variant_gap_planner_overrides
from app.agents.prompt_loader import PromptLoader
from app.agents.runner import AgentRunner
from app.agents.slot_mapper import (
    classify_slot_matches,
    post_validate_slot_matches,
    run_slot_mapper,
)
from app.pipelines.gap_selection import VideoGenQuota
from app.runtime.agent_run_store import AgentRunStore
from app.runtime.task_context import TaskContext
from app.tools.llm_tool import LLMTool, load_agent_fixtures


def _fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures" / "agents"


def _load_structure_fixture() -> dict:
    path = Path(__file__).parent / "fixtures" / "structures" / "sample-structure.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _inventory() -> dict:
    return {
        "id": "inventory-project-1",
        "projectId": "project-1",
        "userBrief": {"sellingPoints": ["便携"], "mustMention": [], "avoidMention": []},
        "assets": [
            {
                "id": "asset-text-1",
                "type": "text",
                "uri": "storage://caption-1.txt",
                "description": "核心卖点文案",
                "tags": ["文案", "卖点"],
            }
        ],
        "extractedFacts": [{"id": "fact-1", "kind": "selling_point", "text": "便携", "source": "brief"}],
        "candidateMoments": [],
    }


def test_post_validate_rewrites_debug_match_reason() -> None:
    structure = _load_structure_fixture()
    inventory = _inventory()
    raw_matches = [
        {
            "slotId": "seg-hook-hook_visual-1",
            "assetId": "asset-text-1",
            "matchScore": 0.9,
            "matchReason": "type=0.50, semantic=0.00, duration=0.60",
        }
    ]
    validated = post_validate_slot_matches(raw_matches, structure=structure, inventory=inventory)
    assert validated
    reason = validated[0]["matchReason"]
    assert "type=" not in reason
    assert validated[0]["matchScore"] < 0.9


def test_classify_slot_matches_thresholds() -> None:
    structure = {
        "slots": [
            {"id": "strong", "importance": "must_have"},
            {"id": "weak", "importance": "must_have"},
            {"id": "missing", "importance": "must_have"},
            {"id": "none", "importance": "must_have"},
        ]
    }
    matches = [
        {"slotId": "strong", "matchScore": 0.7, "matchReason": "强匹配"},
        {"slotId": "weak", "matchScore": 0.5, "matchReason": "弱匹配"},
        {"slotId": "missing", "matchScore": 0.2, "matchReason": "差匹配"},
    ]
    matched, weak_ids, missing_ids = classify_slot_matches(structure, matches)
    assert len(matched) == 2
    assert "weak" in weak_ids
    assert "missing" in missing_ids
    assert "none" in missing_ids


def test_run_slot_mapper_fixture_natural_language(tmp_path: Path) -> None:
    runner = AgentRunner(
        llm=LLMTool(fixture_mode=True, fixtures=load_agent_fixtures(_fixtures_dir())),
        prompt_loader=PromptLoader(),
        run_store=AgentRunStore(tmp_path),
    )
    context = TaskContext(project_id="project-1", task_id="task-1", storage_root=tmp_path)
    structure = _load_structure_fixture()
    inventory = _inventory()
    matches = run_slot_mapper(
        runner,
        structure=structure,
        inventory=inventory,
        context=context,
    )
    assert matches
    for match in matches:
        assert match["matchReason"]
        assert "type=" not in match["matchReason"]


def test_reconcile_gap_buckets_uses_python_classification() -> None:
    structure = _load_structure_fixture()
    inventory = _inventory()
    slot_matches = post_validate_slot_matches(
        json.loads((_fixtures_dir() / "slot_mapper.json").read_text(encoding="utf-8"))["slotMatches"],
        structure=structure,
        inventory=inventory,
    )
    gap_report = json.loads((_fixtures_dir() / "gap_planner.json").read_text(encoding="utf-8"))
    reconciled = reconcile_gap_buckets(
        gap_report,
        structure=structure,
        slot_matches=slot_matches,
    )
    weak_ids = {item["slotId"] for item in reconciled["weakSlots"]}
    missing_ids = {item["slotId"] for item in reconciled["missingSlots"]}
    assert "seg-cta-cta-1" in weak_ids
    assert "seg-hook-hook_text-2" in missing_ids
    assert "seg-2-benefit_card-1" in missing_ids
    assert "seg-3-proof-1" in missing_ids
    assert "seg-hook-hook_visual-1" in missing_ids


def test_load_variant_gap_planner_overrides_from_registry() -> None:
    clear_registry_cache()
    high_click = load_variant_gap_planner_overrides("high_click")
    high_conversion = load_variant_gap_planner_overrides("high_conversion")
    assert high_click.get("videoGenPriority") == "high"
    assert "video_generation" in high_click.get("preferProviders", [])
    assert high_conversion.get("videoGenPriority") == "low"
    assert "image_generation" in high_conversion.get("preferProviders", [])


def test_apply_provider_selection_overrides_suggested_fixes() -> None:
    structure = _load_structure_fixture()
    inventory = _inventory()
    slot_matches = json.loads((_fixtures_dir() / "slot_mapper.json").read_text(encoding="utf-8"))[
        "slotMatches"
    ]
    slot_matches = post_validate_slot_matches(
        slot_matches,
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
    updated = apply_provider_selection(
        gap_report,
        structure=structure,
        slot_matches=slot_matches,
        quota=VideoGenQuota(max_calls=1),
        variant_overrides={"videoGenPriority": "high"},
    )
    missing = updated["missingSlots"][0]
    assert missing["slotId"] == "seg-hook-hook_visual-1"
    assert missing["suggestedFixes"][0] in {
        "image_generation",
        "video_generation",
        "hyperframes_material",
    }
    assert "补全策略：" in missing["reason"]
    weak_cta = next(item for item in updated["weakSlots"] if item["slotId"] == "seg-cta-cta-1")
    assert weak_cta["suggestedFixes"][0] == "asset_reuse"
    assert "补全策略：" in weak_cta["reason"]


def test_run_gap_planner_end_to_end(tmp_path: Path) -> None:
    runner = AgentRunner(
        llm=LLMTool(fixture_mode=True, fixtures=load_agent_fixtures(_fixtures_dir())),
        prompt_loader=PromptLoader(),
        run_store=AgentRunStore(tmp_path),
    )
    context = TaskContext(project_id="project-1", task_id="task-1", storage_root=tmp_path)
    structure = _load_structure_fixture()
    inventory = _inventory()
    slot_matches = post_validate_slot_matches(
        json.loads((_fixtures_dir() / "slot_mapper.json").read_text(encoding="utf-8"))["slotMatches"],
        structure=structure,
        inventory=inventory,
    )
    report = run_gap_planner(
        runner,
        structure=structure,
        inventory=inventory,
        slot_matches=slot_matches,
        context=context,
        variant="high_click",
        quota=VideoGenQuota(max_calls=1),
    )
    assert report["slotMatches"] == slot_matches
    assert report["missingSlots"]
    assert report["weakSlots"]
    assert all("补全策略：" in item["reason"] for item in report["missingSlots"] + report["weakSlots"])
    missing_ids = {item["slotId"] for item in report["missingSlots"]}
    assert "seg-hook-hook_text-2" in missing_ids
