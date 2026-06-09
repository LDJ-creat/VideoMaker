from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

LOGICAL_STAGE_ORDER = ("storyboard", "material", "packaging", "timeline", "render")

LOGICAL_TO_PIPELINE: dict[str, str] = {
    "storyboard": "mapping_slots",
    "material": "generating_material",
    "packaging": "planning_completion",
    "timeline": "building_timeline",
    "render": "rendering",
}

PIPELINE_STAGE_ORDER = (
    "analyzing_assets",
    "mapping_slots",
    "drafting_master_script",
    "drafting_storyboard",
    "planning_completion",
    "generating_material",
    "building_timeline",
    "rendering",
)

OPERATION_LOGICAL_STAGES: dict[str, tuple[str, ...]] = {
    "adjust_hook": ("storyboard", "material", "packaging", "timeline", "render"),
    "reduce_subtitles": ("packaging", "timeline", "render"),
    "increase_subtitles": ("packaging", "timeline", "render"),
    "reorder_selling_points": ("storyboard", "material", "timeline", "render"),
    "change_pace": ("storyboard", "timeline", "render"),
    "change_packaging_style": ("packaging", "material", "timeline", "render"),
    "adjust_cta": ("storyboard", "packaging", "timeline", "render"),
    "subtitle_patch": ("packaging", "timeline", "render"),
    "timeline_scene_patch": ("timeline", "render"),
}

EXECUTION_TOOL_LOGICAL_STAGES: dict[str, tuple[str, ...]] = {
    "subtitle_patch": ("packaging", "timeline", "render"),
    "timeline_scene_patch": ("timeline", "render"),
    "script_revise": ("storyboard", "timeline", "render"),
    "packaging_agent": ("packaging", "timeline", "render"),
    "storyboard_agent": ("storyboard", "material", "timeline", "render"),
    "material_regen": ("material", "timeline", "render"),
    "full_pipeline": ("storyboard", "material", "packaging", "timeline", "render"),
}

_HOOK_MARKERS = ("开头", "hook", "抓人", "更吸引")
_SUBTITLE_REDUCE_MARKERS = ("字幕少", "减少字幕", "fewer subtitle", "less subtitle")
_SUBTITLE_INCREASE_MARKERS = ("字幕多", "增加字幕", "more subtitle")
_REORDER_MARKERS = ("卖点顺序", "reorder selling")
_PACE_MARKERS = ("节奏", "pace", "快一点", "慢一点")
_PACKAGING_MARKERS = ("包装风格", "packaging style")
_CTA_MARKERS = ("cta", "行动号召", "号召")


@dataclass
class ReviseContext:
    generation_params: dict[str, Any] = field(default_factory=dict)
    agent_overrides: dict[str, dict[str, Any]] = field(default_factory=dict)
    affected_pipeline_stages: list[str] = field(default_factory=list)
    rerun_storyboard: bool = True
    rerun_packaging: bool = True


STORYBOARD_OPERATIONS = frozenset(
    {"adjust_hook", "reorder_selling_points", "change_pace", "adjust_cta"}
)
PACKAGING_OPERATIONS = frozenset(
    {
        "adjust_hook",
        "reduce_subtitles",
        "increase_subtitles",
        "change_packaging_style",
        "adjust_cta",
        "subtitle_patch",
    }
)


def _logical_stages_for_intent(intent: dict[str, Any]) -> tuple[str, ...]:
    tool = str(intent.get("executionTool") or "")
    if tool in EXECUTION_TOOL_LOGICAL_STAGES:
        return EXECUTION_TOOL_LOGICAL_STAGES[tool]
    operation = str(intent.get("operation", ""))
    return OPERATION_LOGICAL_STAGES.get(operation, ())


def compute_affected_stages(intents: list[dict[str, Any]]) -> list[str]:
    """Return ordered pipeline stage names to re-run for the given intents."""
    logical: list[str] = []
    seen_logical: set[str] = set()
    for intent in intents:
        for stage in _logical_stages_for_intent(intent):
            if stage not in seen_logical:
                seen_logical.add(stage)
                logical.append(stage)

    logical.sort(key=lambda name: LOGICAL_STAGE_ORDER.index(name))
    pipeline_stages: list[str] = []
    seen_pipeline: set[str] = set()
    for name in logical:
        pipeline_name = LOGICAL_TO_PIPELINE[name]
        if pipeline_name not in seen_pipeline:
            seen_pipeline.add(pipeline_name)
            pipeline_stages.append(pipeline_name)

    pipeline_stages.sort(key=lambda name: PIPELINE_STAGE_ORDER.index(name))
    return pipeline_stages


def apply_intents_to_context(
    intents: list[dict[str, Any]],
    *,
    source_plan: dict[str, Any] | None = None,
    source_timeline: dict[str, Any] | None = None,
) -> ReviseContext:
    _ = source_plan, source_timeline
    generation_params: dict[str, Any] = {}
    agent_overrides: dict[str, dict[str, Any]] = {}

    for intent in intents:
        operation = str(intent.get("operation", ""))
        params = intent.get("params") if isinstance(intent.get("params"), dict) else {}

        if operation == "adjust_hook":
            strength = str(params.get("strength", "high"))
            generation_params["hookStrength"] = strength
            agent_overrides.setdefault("storyboard_writer", {})["hookEmphasis"] = strength
        elif operation == "reduce_subtitles":
            generation_params["subtitleDensity"] = "low"
            agent_overrides.setdefault("packaging_designer", {})["subtitleDensity"] = "low"
        elif operation == "increase_subtitles":
            generation_params["subtitleDensity"] = "high"
            agent_overrides.setdefault("packaging_designer", {})["subtitleDensity"] = "high"
        elif operation == "reorder_selling_points":
            generation_params["reorderSellingPoints"] = True
            agent_overrides.setdefault("storyboard_writer", {})["reorderSellingPoints"] = True
        elif operation == "change_pace":
            direction = str(params.get("direction", "faster"))
            generation_params["pace"] = direction
            agent_overrides.setdefault("storyboard_writer", {})["pace"] = direction
        elif operation == "change_packaging_style":
            style = str(params.get("style", "bold"))
            generation_params["packagingStyle"] = style
            agent_overrides.setdefault("packaging_designer", {})["style"] = style
        elif operation == "adjust_cta":
            strength = str(params.get("strength", "high"))
            generation_params["ctaStrength"] = strength
            agent_overrides.setdefault("storyboard_writer", {})["ctaEmphasis"] = strength
            agent_overrides.setdefault("packaging_designer", {})["ctaEmphasis"] = strength
        elif operation == "subtitle_patch":
            density = str(params.get("density", "low"))
            generation_params["subtitleDensity"] = density
            agent_overrides.setdefault("packaging_designer", {})["subtitleDensity"] = density
        elif operation == "timeline_scene_patch":
            generation_params["timelineScenePatch"] = dict(params)

    affected = compute_affected_stages(intents)
    rerun_storyboard = any(str(i.get("operation", "")) in STORYBOARD_OPERATIONS for i in intents)
    rerun_packaging = any(str(i.get("operation", "")) in PACKAGING_OPERATIONS for i in intents)
    return ReviseContext(
        generation_params=generation_params,
        agent_overrides=agent_overrides,
        affected_pipeline_stages=affected,
        rerun_storyboard=rerun_storyboard,
        rerun_packaging=rerun_packaging,
    )


def build_source_summary(plan: dict[str, Any]) -> dict[str, Any]:
    timeline = plan.get("timeline") if isinstance(plan.get("timeline"), dict) else {}
    packaging = plan.get("packagingPlan") if isinstance(plan.get("packagingPlan"), dict) else {}
    subtitle = packaging.get("subtitle") if isinstance(packaging.get("subtitle"), dict) else {}
    density = subtitle.get("density") or packaging.get("visualDensity") or "medium"
    storyboard = plan.get("storyboard") if isinstance(plan.get("storyboard"), list) else []
    return {
        "variant": str(plan.get("variant", "default")),
        "storyboardSceneCount": len(storyboard),
        "timelineDurationSec": float(timeline.get("durationSec", 0.0) or 0.0),
        "packagingDensity": str(density),
    }


def parse_edit_intent_for_api(instruction: str, source_summary: dict[str, Any]) -> dict[str, Any]:
    """Deterministic NL mapping for API sync response (mirrors fixture for common phrases)."""
    _ = source_summary
    text = instruction.strip().lower()
    intents: list[dict[str, Any]] = []

    if any(marker in instruction or marker in text for marker in _HOOK_MARKERS):
        intents.append(
            {
                "target": "generation_plan.storyboard",
                "operation": "adjust_hook",
                "params": {"strength": "high"},
                "rationale": "用户希望开头更抓人",
            }
        )
    if any(marker in instruction or marker in text for marker in _SUBTITLE_REDUCE_MARKERS):
        intents.append(
            {
                "target": "generation_plan.packaging",
                "operation": "reduce_subtitles",
                "params": {},
                "rationale": "用户希望减少字幕",
                "scope": "track_subtitle",
                "executionTool": "subtitle_patch",
            }
        )
    if any(marker in instruction or marker in text for marker in _SUBTITLE_INCREASE_MARKERS):
        intents.append(
            {
                "target": "generation_plan.packaging",
                "operation": "increase_subtitles",
                "params": {},
                "rationale": "用户希望增加字幕",
                "scope": "track_subtitle",
                "executionTool": "subtitle_patch",
            }
        )
    if any(marker in instruction or marker in text for marker in _REORDER_MARKERS):
        intents.append(
            {
                "target": "generation_plan.storyboard",
                "operation": "reorder_selling_points",
                "params": {},
                "rationale": "用户希望调整卖点顺序",
            }
        )
    if any(marker in instruction or marker in text for marker in _PACE_MARKERS):
        intents.append(
            {
                "target": "generation_plan.storyboard",
                "operation": "change_pace",
                "params": {"direction": "faster"},
                "rationale": "用户希望调整节奏",
            }
        )
    if any(marker in instruction or marker in text for marker in _PACKAGING_MARKERS):
        intents.append(
            {
                "target": "generation_plan.packaging",
                "operation": "change_packaging_style",
                "params": {},
                "rationale": "用户希望调整包装风格",
            }
        )
    if any(marker in instruction or marker in text for marker in _CTA_MARKERS):
        intents.append(
            {
                "target": "generation_plan.storyboard",
                "operation": "adjust_cta",
                "params": {"strength": "high"},
                "rationale": "用户希望强化行动号召",
            }
        )

    if not intents:
        raise ValueError("Could not parse any edit intents from instruction")

    return {"intents": intents}


def validate_edit_intents(intents: list[dict[str, Any]]) -> None:
    from app.validation.schema_loader import validate_contract

    validation = validate_contract("edit-intent", {"intents": intents})
    if validation.valid:
        return
    messages = [item.message for item in validation.errors]
    raise ValueError(f"Invalid EditIntent payload: {'; '.join(messages)}")
