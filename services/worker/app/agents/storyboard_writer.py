from __future__ import annotations

from typing import Any

from app.agents.runner import AgentRunner
from app.config.variants import load_agent_overrides
from app.pipelines.master_narration import apply_master_narration_to_storyboard
from app.pipelines.narration_script import is_creative_direction_text
from app.pipelines.visual_style_bible import (
    knowledge_entry_id_from_context,
    normalize_visual_style_bible,
)
from app.runtime.task_context import TaskContext


TASK_KEY = "storyboard_writer"
VALID_SOURCES = {
    "user_asset",
    "text_completion",
    "packaging_completion",
    "asset_reuse",
    "generated",
}
VALID_PHASES = {
    "master_only",
    "storyboard_from_master",
    "revise_master",
    "revise_storyboard",
}
DEPRECATED_PHASES = {"full"}


def slim_structure_for_script(structure: dict[str, Any]) -> dict[str, Any]:
    """Drop perception-heavy blocks that add tokens without helping script writing."""
    if not isinstance(structure, dict):
        return {}
    slim: dict[str, Any] = {}
    for key in ("id", "projectId", "sourceVideoId", "version", "confidence"):
        if key in structure:
            slim[key] = structure[key]
    metadata = structure.get("metadata")
    if isinstance(metadata, dict):
        slim["metadata"] = metadata
    narrative = structure.get("narrative")
    if isinstance(narrative, dict):
        slim["narrative"] = narrative
    slots = structure.get("slots")
    if isinstance(slots, list):
        slim["slots"] = slots
    for block in ("context", "verbal", "visual", "audio", "transfer"):
        value = structure.get(block)
        if isinstance(value, dict):
            slim[block] = value
    rhythm = structure.get("rhythm")
    if isinstance(rhythm, dict):
        slim["rhythm"] = {
            key: rhythm[key]
            for key in ("totalDurationSec", "tempo", "beatPoints", "avgShotDurationSec", "shotCount")
            if key in rhythm
        }
    return slim


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


def _optional_summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = str(payload.get("summary") or "").strip()
    return {"summary": summary} if summary else {}


def _assert_master_only(
    payload: dict[str, Any],
    *,
    structure: dict[str, Any],
    knowledge_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    master = str(payload.get("masterNarration") or "").strip()
    if not master:
        raise ValueError("storyboard_writer master_only output must include non-empty masterNarration")
    knowledge_entry_id = knowledge_entry_id_from_context(knowledge_context)
    bible = normalize_visual_style_bible(
        payload.get("visualStyleBible") if isinstance(payload.get("visualStyleBible"), dict) else None,
        structure=structure,
        knowledge_entry_id=knowledge_entry_id,
    )
    result: dict[str, Any] = {
        "masterNarration": master,
        "visualStyleBible": bible,
        **_optional_summary(payload),
    }
    return result


def _assert_storyboard_from_master(
    payload: dict[str, Any],
    *,
    structure: dict[str, Any],
    master_narration: str,
) -> dict[str, Any]:
    storyboard = payload.get("storyboard")
    if not isinstance(storyboard, list):
        raise ValueError("storyboard_writer storyboard_from_master output must include storyboard array")
    normalized = _normalize_storyboard_scenes(storyboard, structure=structure)
    master = str(master_narration or payload.get("masterNarration") or "").strip()
    if not master:
        raise ValueError("approved masterNarration is required for storyboard_from_master")
    _, aligned = apply_master_narration_to_storyboard(
        master_narration=master,
        storyboard=normalized,
        structure=structure,
    )
    return {"storyboard": aligned, **_optional_summary(payload)}


def _assert_storyboard(
    payload: dict[str, Any],
    *,
    structure: dict[str, Any],
) -> dict[str, Any]:
    """Legacy one-shot validator — retained for unit tests only."""
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
    phase: str,
    progress: int = 52,
    generation_id: str | None = None,
    variant: str = "default",
    agent_overrides: dict[str, Any] | None = None,
    knowledge_context: dict[str, Any] | None = None,
    master_narration: str | None = None,
    visual_style_bible: dict[str, Any] | None = None,
    duration_target: dict[str, Any] | None = None,
    instruction: str | None = None,
    current_storyboard: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    normalized_phase = str(phase or "").strip()
    if normalized_phase in DEPRECATED_PHASES:
        raise ValueError(
            f"storyboard_writer phase '{normalized_phase}' is deprecated; "
            "use master_only then storyboard_from_master"
        )
    if normalized_phase not in VALID_PHASES:
        raise ValueError(f"Invalid storyboard_writer phase: {normalized_phase}")

    variant_overrides = load_agent_overrides(variant, "storyboard_writer")
    if agent_overrides:
        variant_overrides = {**variant_overrides, **agent_overrides}
    inputs: dict[str, Any] = {
        "structureForScript": slim_structure_for_script(structure),
        "inventory": inventory,
        "gapReport": gap_report,
        "variantOverrides": variant_overrides,
        "phase": normalized_phase,
    }
    if duration_target is not None:
        inputs["durationTarget"] = duration_target
    if master_narration is not None:
        inputs["masterNarration"] = master_narration
    if visual_style_bible is not None:
        inputs["visualStyleBible"] = visual_style_bible
    if instruction is not None:
        inputs["instruction"] = instruction
    if current_storyboard is not None:
        inputs["storyboard"] = current_storyboard
    if knowledge_context:
        inputs["knowledgeContext"] = knowledge_context

    if normalized_phase in {"master_only", "revise_master"}:
        post_validate = lambda payload: _assert_master_only(
            payload,
            structure=structure,
            knowledge_context=knowledge_context,
        )
    else:
        approved_master = str(master_narration or "").strip()
        locked_bible = visual_style_bible
        if locked_bible is None and normalized_phase == "storyboard_from_master":
            knowledge_entry_id = knowledge_entry_id_from_context(knowledge_context)
            locked_bible = normalize_visual_style_bible(None, structure=structure, knowledge_entry_id=knowledge_entry_id)
        if locked_bible is not None and normalized_phase in {"storyboard_from_master", "revise_storyboard"}:
            inputs["visualStyleBible"] = locked_bible
        post_validate = lambda payload: _assert_storyboard_from_master(
            payload,
            structure=structure,
            master_narration=approved_master,
        )

    output = runner.run(
        "storyboard_writer",
        task=TASK_KEY,
        schema_name=None,
        inputs=inputs,
        context=context,
        progress=progress,
        generation_id=generation_id,
        post_validate=post_validate,
    )
    return output
