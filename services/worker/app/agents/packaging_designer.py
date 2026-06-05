from __future__ import annotations

from typing import Any

from app.agents.runner import AgentRunner
from app.config.variants import load_agent_overrides
from app.runtime.task_context import TaskContext
from app.validation.schema_loader import validate_contract


TASK_KEY = "packaging_designer"


def _normalize_packaging_plan(
    packaging_plan: dict[str, Any],
    *,
    structure: dict[str, Any],
) -> dict[str, Any]:
    source = dict(packaging_plan)
    sample_packaging = structure.get("packaging")
    sample_packaging = sample_packaging if isinstance(sample_packaging, dict) else {}

    style_summary = str(source.get("styleSummary") or source.get("style_summary") or "").strip()
    if not style_summary:
        density = source.get("visualDensity") or sample_packaging.get("visualDensity")
        style_summary = (
            f"Visual density: {density}" if density is not None else "Short-form product promo"
        )

    subtitle = source.get("subtitle")
    if not isinstance(subtitle, dict):
        subtitle = {}
    text_hints = source.get("textStyleHints")
    if isinstance(text_hints, dict):
        subtitle = {**subtitle, **text_hints}
    text_overlays = source.get("textOverlays")
    if isinstance(text_overlays, dict) and "preset" not in subtitle:
        subtitle = {**subtitle, **text_overlays}
    if not subtitle:
        subtitle = {"preset": "clean"}

    title_cards = source.get("titleCards")
    if not isinstance(title_cards, list):
        stickers = source.get("stickers")
        title_cards = stickers if isinstance(stickers, list) else []
    if not title_cards:
        sample_cards = sample_packaging.get("titleCards")
        title_cards = list(sample_cards) if isinstance(sample_cards, list) and sample_cards else [{"preset": "hook"}]

    transitions = source.get("transitions")
    if not isinstance(transitions, list):
        transitions = []
    if not transitions:
        sample_transitions = sample_packaging.get("transitions")
        transitions = (
            list(sample_transitions)
            if isinstance(sample_transitions, list) and sample_transitions
            else [{"preset": "quick-cut"}]
        )

    return {
        "styleSummary": style_summary,
        "subtitle": subtitle,
        "titleCards": title_cards,
        "transitions": transitions,
    }


def _assert_packaging_plan(
    payload: dict[str, Any],
    *,
    structure: dict[str, Any],
) -> dict[str, Any]:
    packaging_plan = payload.get("packagingPlan")
    if not isinstance(packaging_plan, dict):
        raise ValueError("packaging_designer output must include packagingPlan object")
    normalized_plan = _normalize_packaging_plan(packaging_plan, structure=structure)
    probe = {
        "id": "plan-probe",
        "projectId": "probe",
        "structureId": "probe",
        "inventoryId": "probe",
        "gapReportId": "probe",
        "variant": "default",
        "masterNarration": "",
        "storyboard": [],
        "timeline": {"durationSec": 0.0, "tracks": []},
        "packagingPlan": normalized_plan,
        "completionActions": [],
    }
    validation = validate_contract("generation-plan", probe)
    if not validation.valid:
        raise ValueError(f"Invalid packagingPlan: {validation.errors}")
    return {**payload, "packagingPlan": normalized_plan}


def _collect_on_screen_text(structure: dict[str, Any]) -> list[str]:
    texts: list[str] = []
    narrative = structure.get("narrative")
    if not isinstance(narrative, dict):
        return texts
    for segment in narrative.get("segments") or []:
        if not isinstance(segment, dict):
            continue
        visual_spec = segment.get("visualSpec")
        if isinstance(visual_spec, dict):
            for item in visual_spec.get("onScreenText") or []:
                text = str(item).strip()
                if text and text not in texts:
                    texts.append(text)
    return texts


def run_packaging_designer(
    runner: AgentRunner,
    *,
    structure: dict[str, Any],
    storyboard: list[dict[str, Any]],
    context: TaskContext,
    progress: int = 58,
    generation_id: str | None = None,
    variant: str = "default",
    agent_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    variant_overrides = load_agent_overrides(variant, "packaging_designer")
    if agent_overrides:
        variant_overrides = {**variant_overrides, **agent_overrides}
    output = runner.run(
        "packaging_designer",
        task=TASK_KEY,
        schema_name=None,
        inputs={
            "structure": structure,
            "storyboard": storyboard,
            "variantOverrides": variant_overrides,
            "onScreenTextStyles": _collect_on_screen_text(structure),
            "packagingRequirements": [
                requirement
                for slot in structure.get("slots") or []
                if isinstance(slot, dict)
                for requirement in (slot.get("packagingRequirements") or [])
            ],
        },
        context=context,
        progress=progress,
        generation_id=generation_id,
        post_validate=lambda payload: _assert_packaging_plan(payload, structure=structure),
    )
    return output["packagingPlan"]
