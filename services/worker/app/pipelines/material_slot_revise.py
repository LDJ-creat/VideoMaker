from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.pipelines.display_copy_policy import (
    apply_display_copy_to_finish_brief,
    build_author_contract,
    derive_allowed_display_copy,
    infer_material_edit_mode_for_gate_revise,
)
from app.pipelines.material_review_state import (
    load_material_slot_revise_queue,
    write_material_slot_revise_queue,
)
from app.pipelines.revise_material_edit import (
    GENERATION_PLAN_FILENAME,
    SlotChainKind,
    archive_slot_material,
    build_edit_finish_brief,
    classify_slot_material_chain,
    is_terminal_hf_action,
)
from app.providers.completion_registry import invalidate_material_for_slots

REVISE_CONTEXT_FILENAME = "revise-context.json"
MATERIAL_GATE_REVISE_SOURCE = "material_gate_revise"
MATERIAL_GATE_REVISE_KEY = "materialGateRevise"
_LEGACY_GATE_KEYS = (
    "source",
    "materialEditMode",
    "editInstruction",
    "slotChainKinds",
)

_ACP_SCRATCH_ARTIFACTS = (
    "material-spec.json",
    "material-spec.lint-passed",
    "material-review-marker.json",
    "_draft_spec.json",
    "_mcp_call.py",
)


def _load_revise_context_payload(generation_root: Path) -> dict[str, Any]:
    context_path = generation_root / REVISE_CONTEXT_FILENAME
    if not context_path.is_file():
        return {}
    try:
        payload = json.loads(context_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_revise_context_payload(generation_root: Path, payload: dict[str, Any]) -> None:
    context_path = generation_root / REVISE_CONTEXT_FILENAME
    context_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _storyboard_scene_for_slot(
    *,
    generation_root: Path,
    plan: dict[str, Any],
    slot_id: str,
) -> dict[str, Any] | None:
    storyboard = plan.get("storyboard")
    if not isinstance(storyboard, list):
        plan_path = generation_root / GENERATION_PLAN_FILENAME
        if plan_path.is_file():
            try:
                loaded = json.loads(plan_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                loaded = {}
            if isinstance(loaded, dict):
                storyboard = loaded.get("storyboard")
    if not isinstance(storyboard, list):
        return None
    for scene in storyboard:
        if isinstance(scene, dict) and str(scene.get("slotId") or "") == slot_id:
            return dict(scene)
    return None


def _finish_brief_from_actions(actions: list[dict[str, Any]], slot_id: str) -> dict[str, Any]:
    terminal: dict[str, Any] | None = None
    for action in actions:
        if not isinstance(action, dict):
            continue
        if str(action.get("slotId") or "") != slot_id:
            continue
        finish_brief = action.get("finishBrief")
        if isinstance(finish_brief, dict):
            if is_terminal_hf_action(action):
                return dict(finish_brief)
            terminal = dict(finish_brief)
    return terminal or {}


def _patch_slot_finish_briefs(
    actions: list[dict[str, Any]],
    slot_id: str,
    finish_brief: dict[str, Any],
) -> None:
    for action in actions:
        if not isinstance(action, dict):
            continue
        if str(action.get("slotId") or "") != slot_id:
            continue
        if is_terminal_hf_action(action) or str(action.get("provider") or "") == "hyperframes_material":
            action["finishBrief"] = dict(finish_brief)


def clear_acp_scratch_for_gate_revise(generation_root: Path, slot_id: str) -> None:
    scratch = generation_root / "acp-author" / slot_id
    if not scratch.is_dir():
        return
    for name in _ACP_SCRATCH_ARTIFACTS:
        (scratch / name).unlink(missing_ok=True)


def queue_material_slot_revise(
    *,
    generation_root: Path,
    generation_id: str,
    slot_id: str,
    instruction: str,
    requested_by: str = "user",
) -> dict[str, Any]:
    payload = {
        "generationId": generation_id,
        "slotId": slot_id,
        "instruction": instruction.strip(),
        "requestedBy": requested_by,
        "status": "pending",
    }
    write_material_slot_revise_queue(generation_root, payload)
    return payload


def consume_material_slot_revise_queue(generation_root: Path) -> dict[str, Any] | None:
    queue = load_material_slot_revise_queue(generation_root)
    if not isinstance(queue, dict):
        return None
    if str(queue.get("status") or "") != "pending":
        return None
    return queue


def prepare_material_slot_revise(
    *,
    generation_root: Path,
    plan: dict[str, Any],
    slot_id: str,
    instruction: str,
) -> tuple[dict[str, Any], set[str]]:
    completion_actions = list(plan.get("completionActions") or [])
    chain = classify_slot_material_chain(completion_actions, slot_id)
    generated_root = generation_root / "generated"
    material_state_path = generation_root / "material-state.json"
    archive_slot_material(
        generation_root=generation_root,
        generated_root=generated_root,
        actions=completion_actions,
        slot_id=slot_id,
    )
    invalidate_material_for_slots(
        actions=completion_actions,
        generated_root=generated_root,
        slot_ids={slot_id},
        material_state_path=material_state_path,
        clear_material_gate=True,
        generation_root=generation_root,
    )
    clear_acp_scratch_for_gate_revise(generation_root, slot_id)

    storyboard_scene = _storyboard_scene_for_slot(
        generation_root=generation_root,
        plan=plan,
        slot_id=slot_id,
    )
    base_finish_brief = _finish_brief_from_actions(completion_actions, slot_id)
    edited_brief = build_edit_finish_brief(base_finish_brief, instruction=instruction)
    patched_brief = apply_display_copy_to_finish_brief(
        edited_brief,
        edit_instruction=instruction,
        storyboard_scene=storyboard_scene,
    )
    _patch_slot_finish_briefs(completion_actions, slot_id, patched_brief)
    plan["completionActions"] = completion_actions

    edit_mode = infer_material_edit_mode_for_gate_revise(instruction)
    allowed = derive_allowed_display_copy(
        finish_brief=patched_brief,
        edit_instruction=instruction,
        storyboard_scene=storyboard_scene,
        composition_author_brief=patched_brief.get("compositionAuthorBrief")
        if isinstance(patched_brief.get("compositionAuthorBrief"), dict)
        else None,
    )
    author_contract = build_author_contract(
        allowed_display_copy=allowed,
        material_edit_mode=edit_mode,
        must_change_spec=True,
    )

    payload = _load_revise_context_payload(generation_root)
    payload[MATERIAL_GATE_REVISE_KEY] = {
        "source": MATERIAL_GATE_REVISE_SOURCE,
        "materialEditMode": edit_mode,
        "editInstruction": instruction,
        "affectedSlotIds": [slot_id],
        "slotChainKinds": {slot_id: chain.value},
        "authorContract": author_contract,
        "allowedDisplayCopy": allowed,
    }
    _write_revise_context_payload(generation_root, payload)

    queue = load_material_slot_revise_queue(generation_root)
    if isinstance(queue, dict):
        queue["status"] = "consumed"
        write_material_slot_revise_queue(generation_root, queue)
    return plan, {slot_id}


def clear_material_gate_revise_context(generation_root: Path) -> None:
    payload = _load_revise_context_payload(generation_root)
    if not payload:
        return
    gate = payload.get(MATERIAL_GATE_REVISE_KEY)
    if isinstance(gate, dict) and gate.get("source") == MATERIAL_GATE_REVISE_SOURCE:
        payload.pop(MATERIAL_GATE_REVISE_KEY, None)
    elif payload.get("source") == MATERIAL_GATE_REVISE_SOURCE:
        for key in _LEGACY_GATE_KEYS:
            payload.pop(key, None)
        if not payload.get("sourceGenerationId") and not payload.get("materialReviewScope"):
            context_path = generation_root / REVISE_CONTEXT_FILENAME
            context_path.unlink(missing_ok=True)
            return
    else:
        return
    if payload:
        _write_revise_context_payload(generation_root, payload)
    else:
        (generation_root / REVISE_CONTEXT_FILENAME).unlink(missing_ok=True)


def slot_chain_for_action(plan: dict[str, Any], slot_id: str) -> SlotChainKind:
    return classify_slot_material_chain(list(plan.get("completionActions") or []), slot_id)


def load_material_gate_revise_slot_ids(generation_root: Path) -> set[str] | None:
    """Return scoped slot ids for an in-progress material gate NL revise (queue may already be consumed)."""
    payload = _load_revise_context_payload(generation_root)
    gate = payload.get(MATERIAL_GATE_REVISE_KEY)
    if not isinstance(gate, dict):
        return None
    if gate.get("source") != MATERIAL_GATE_REVISE_SOURCE:
        return None
    slot_ids = gate.get("affectedSlotIds")
    if not isinstance(slot_ids, list):
        return None
    filtered = {str(item).strip() for item in slot_ids if str(item).strip()}
    return filtered or None
