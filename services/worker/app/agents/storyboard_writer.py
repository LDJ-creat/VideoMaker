from __future__ import annotations

from typing import Any

from app.agents.runner import AgentRunner
from app.config.variants import load_agent_overrides
from app.pipelines.master_narration import apply_master_narration_to_storyboard
from app.pipelines.narration_script import is_creative_direction_text
from app.runtime.task_context import TaskContext


TASK_KEY = "storyboard_writer"
VALID_SOURCES = {
    "user_asset",
    "text_completion",
    "packaging_completion",
    "asset_reuse",
    "generated",
}


def _slot_lookup(structure: dict[str, Any]) -> dict[str, dict[str, Any]]:
    slots = structure.get("slots", [])
    if not isinstance(slots, list):
        return {}
    lookup: dict[str, dict[str, Any]] = {}
    for slot in slots:
        if isinstance(slot, dict) and slot.get("id"):
            lookup[str(slot["id"])] = slot
    return lookup


def _normalize_storyboard_scenes(
    storyboard: list[Any],
    *,
    structure: dict[str, Any],
) -> list[dict[str, Any]]:
    slots_by_id = _slot_lookup(structure)
    normalized: list[dict[str, Any]] = []
    for index, scene in enumerate(storyboard):
        if not isinstance(scene, dict):
            raise ValueError("storyboard items must be objects")
        item = dict(scene)
        slot_id = str(item.get("slotId") or item.get("slot_id") or "").strip()
        slot = slots_by_id.get(slot_id) if slot_id else None
        if not slot_id and slot is None and len(slots_by_id) == 1:
            slot_id, slot = next(iter(slots_by_id.items()))
        if not slot_id and slot is None and index < len(slots_by_id):
            slot_id = str(list(slots_by_id.keys())[index])
            slot = slots_by_id.get(slot_id)

        scene_id = str(item.get("id") or item.get("sceneId") or "").strip()
        if not scene_id:
            scene_id = f"scene-{slot_id}" if slot_id else f"scene-{index + 1}"
        item["id"] = scene_id
        item["slotId"] = slot_id or f"slot-{index + 1}"

        if item.get("startSec") is None and slot is not None:
            item["startSec"] = slot.get("startSec", 0.0)
        if item.get("endSec") is None and slot is not None:
            item["endSec"] = slot.get("endSec", item.get("startSec", 0.0))
        item["startSec"] = float(item.get("startSec", 0.0))
        item["endSec"] = float(item.get("endSec", item["startSec"]))

        item["visual"] = str(
            item.get("visual")
            or item.get("visualIntent")
            or (slot or {}).get("visualIntent")
            or "",
        )
        script = str(item.get("script") or "").strip()
        if not script:
            script = ""
        elif is_creative_direction_text(
            script,
            slot=slot,
            visual=str(item["visual"]),
        ):
            script = ""
        item["script"] = script
        source = str(item.get("source") or "generated").strip()
        if source not in VALID_SOURCES:
            source = "generated"
        item["source"] = source

        normalized.append(
            {
                "id": item["id"],
                "slotId": item["slotId"],
                "startSec": item["startSec"],
                "endSec": item["endSec"],
                "visual": item["visual"],
                "script": item["script"],
                "source": item["source"],
            }
        )
    return normalized


def _assert_storyboard(
    payload: dict[str, Any],
    *,
    structure: dict[str, Any],
) -> dict[str, Any]:
    storyboard = payload.get("storyboard")
    if not isinstance(storyboard, list):
        raise ValueError("storyboard_writer output must include storyboard array")
    required = {"id", "slotId", "startSec", "endSec", "visual", "script", "source"}
    normalized = _normalize_storyboard_scenes(storyboard, structure=structure)
    for scene in normalized:
        missing = required - set(scene.keys())
        if missing:
            raise ValueError(f"storyboard scene missing fields: {sorted(missing)}")

    master_narration, aligned = apply_master_narration_to_storyboard(
        master_narration=str(payload.get("masterNarration", "")),
        storyboard=normalized,
        structure=structure,
    )
    if not master_narration.strip():
        raise ValueError("storyboard_writer output must include non-empty masterNarration")
    return {"masterNarration": master_narration, "storyboard": aligned}


def run_storyboard_writer(
    runner: AgentRunner,
    *,
    structure: dict[str, Any],
    inventory: dict[str, Any],
    gap_report: dict[str, Any],
    context: TaskContext,
    progress: int = 52,
    generation_id: str | None = None,
    variant: str = "default",
    agent_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    variant_overrides = load_agent_overrides(variant, "storyboard_writer")
    if agent_overrides:
        variant_overrides = {**variant_overrides, **agent_overrides}
    output = runner.run(
        "storyboard_writer",
        task=TASK_KEY,
        schema_name=None,
        inputs={
            "structure": structure,
            "inventory": inventory,
            "gapReport": gap_report,
            "variantOverrides": variant_overrides,
        },
        context=context,
        progress=progress,
        generation_id=generation_id,
        post_validate=lambda payload: _assert_storyboard(payload, structure=structure),
    )
    return output
