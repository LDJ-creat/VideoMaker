from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.pipelines.intent_applier import (
    PIPELINE_STAGE_ORDER,
    apply_intents_to_context,
    compute_affected_stages,
)


def _fixture_intents() -> list[dict[str, Any]]:
    return [
        {
            "target": "generation_plan.storyboard",
            "operation": "adjust_hook",
            "params": {"strength": "high"},
            "rationale": "用户希望开头更抓人",
        },
        {
            "target": "generation_plan.packaging",
            "operation": "reduce_subtitles",
            "params": {},
            "rationale": "用户希望减少字幕",
        },
    ]


def test_compute_affected_stages_adjust_hook_and_reduce_subtitles() -> None:
    stages = compute_affected_stages(_fixture_intents())
    assert stages == [
        "mapping_slots",
        "planning_completion",
        "generating_material",
        "building_timeline",
        "rendering",
    ]


def test_compute_affected_stages_reduce_subtitles_only() -> None:
    intents = [
        {
            "target": "generation_plan.packaging",
            "operation": "reduce_subtitles",
            "params": {},
            "rationale": "less subtitles",
        }
    ]
    assert compute_affected_stages(intents) == [
        "planning_completion",
        "building_timeline",
        "rendering",
    ]


def test_compute_affected_stages_change_pace() -> None:
    intents = [
        {
            "target": "generation_plan.storyboard",
            "operation": "change_pace",
            "params": {"direction": "faster"},
            "rationale": "faster",
        }
    ]
    assert compute_affected_stages(intents) == [
        "mapping_slots",
        "building_timeline",
        "rendering",
    ]


def test_apply_intents_sets_generation_params() -> None:
    context = apply_intents_to_context(_fixture_intents(), source_plan={}, source_timeline={})
    assert context.generation_params["hookStrength"] == "high"
    assert context.generation_params["subtitleDensity"] == "low"
    assert context.agent_overrides["storyboard_writer"]["hookEmphasis"] == "high"
    assert context.agent_overrides["packaging_designer"]["subtitleDensity"] == "low"
    assert context.affected_pipeline_stages[0] == "mapping_slots"


def test_apply_intents_sets_rerun_flags() -> None:
    packaging_only = apply_intents_to_context(
        [
            {
                "target": "generation_plan.packaging",
                "operation": "reduce_subtitles",
                "params": {},
                "rationale": "less subtitles",
            }
        ],
        source_plan={},
        source_timeline={},
    )
    assert packaging_only.rerun_storyboard is False
    assert packaging_only.rerun_packaging is True

    hook_only = apply_intents_to_context(
        [
            {
                "target": "generation_plan.storyboard",
                "operation": "adjust_hook",
                "params": {"strength": "high"},
                "rationale": "hook",
            }
        ],
        source_plan={},
        source_timeline={},
    )
    assert hook_only.rerun_storyboard is True
    assert hook_only.rerun_packaging is True


@pytest.mark.parametrize(
    ("operation", "first_stage"),
    [
        ("adjust_hook", "mapping_slots"),
        ("reduce_subtitles", "planning_completion"),
        ("reorder_selling_points", "mapping_slots"),
        ("change_packaging_style", "planning_completion"),
    ],
)
def test_each_operation_maps_to_expected_first_stage(operation: str, first_stage: str) -> None:
    stages = compute_affected_stages(
        [
            {
                "target": "generation_plan.storyboard",
                "operation": operation,
                "params": {},
                "rationale": "test",
            }
        ]
    )
    assert stages[0] == first_stage
    assert stages == sorted(stages, key=PIPELINE_STAGE_ORDER.index)
