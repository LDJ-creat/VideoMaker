from __future__ import annotations

import os
from typing import Any, Callable

from app.validation.schema_loader import validate_contract
from structure.slot_roles import PACKAGING_ROLES, is_packaging_role, normalize_slot_role

VALID_BRIEF_MODES = frozenset({"hf_native", "source_then_polish", "polish_only", "packaging_only"})
VALID_TEMPLATE_PREFERENCES = frozenset(
    {"composition", "benefit-card", "title-lower-third", "ken-burns"}
)
_HF_COMPLETION_MODES = frozenset({"hf_native", "packaging_only", "source_then_polish"})
_AUTHOR_PROMPT_MAX_LEN = 600

_LAYOUT_ANCHOR_BY_MODE: dict[str, str] = {
    "hf_native": "center",
    "packaging_only": "center",
    "source_then_polish": "lower_third",
    "polish_only": "lower_third",
}

_LAYOUT_ANCHOR_POLISH_BY_ROLE: dict[str, str] = {
    "hook_text": "upper_third",
    "hook_visual": "upper_third",
    "cta": "lower_third",
}

_LAYOUT_DIRECTIVES: dict[str, str] = {
    "center": (
        "主信息区必须在竖屏安全区内垂直水平居中（约 35%–55% 垂直带）；"
        "禁止 justify-content:flex-end、align-items:flex-end、bottom 锚定主文案，"
        "避免与 timeline 底部字幕轨重叠。"
    ),
    "lower_third": (
        "保留底片人物居中/偏上；overlay 仅在下方三分之一细条，不遮挡人脸；"
        "禁止在 HF 内重复口播字幕。"
    ),
    "upper_third": (
        "保留底片人物居中；hook/标题 overlay 在上方三分之一，不遮挡面部。"
    ),
}

_BOTTOM_LAYOUT_SIGNALS = (
    "lower third",
    "lower_third",
    "lower-third",
    "对比条",
    "贴底",
    "底部",
    "flex-end",
)


def layout_directive_for_anchor(anchor: str) -> str:
    return _LAYOUT_DIRECTIVES.get(str(anchor or "").strip(), _LAYOUT_DIRECTIVES["center"])


def infer_layout_anchor(
    *,
    mode: str,
    slot: dict[str, Any],
) -> str:
    if mode in {"hf_native", "packaging_only"}:
        return "center"
    role = normalize_slot_role(str(slot.get("role") or ""))
    return _LAYOUT_ANCHOR_POLISH_BY_ROLE.get(role, _LAYOUT_ANCHOR_BY_MODE.get(mode, "lower_third"))


def author_prompt_conflicts_layout_anchor(author_prompt: str, layout_anchor: str) -> bool:
    text = str(author_prompt or "").lower()
    if layout_anchor == "center":
        return any(signal in text for signal in _BOTTOM_LAYOUT_SIGNALS)
    return False


def append_layout_hint_to_author_prompt(author_prompt: str, layout_anchor: str) -> str:
    prompt = str(author_prompt or "").strip()
    anchor = str(layout_anchor or "").strip()
    if not prompt or anchor != "center":
        return prompt
    if any(token in prompt for token in ("垂直居中", "画面居中", "居中排版", "主信息居中")):
        return prompt
    hint = "主信息垂直水平居中，禁止贴底 lower third。"
    combined = f"{prompt}；{hint}" if prompt else hint
    if len(combined) > _AUTHOR_PROMPT_MAX_LEN:
        return combined[:_AUTHOR_PROMPT_MAX_LEN]
    return combined

_TEMPLATE_BY_ROLE: dict[str, str] = {
    "benefit_card": "benefit-card",
    "hook_text": "title-lower-third",
    "comparison": "composition",
    "cta": "composition",
    "transition": "composition",
    "proof": "composition",
}


def composition_brief_mode() -> str:
    raw = os.getenv("VIDEOMAKER_COMPOSITION_BRIEF_MODE", "require").strip().lower()
    if raw in {"off", "warn", "require"}:
        return raw
    return "require"


def gap_item_for_slot(gap_report: dict[str, Any] | None, slot_id: str) -> dict[str, Any] | None:
    if not isinstance(gap_report, dict) or not slot_id:
        return None
    for key in ("weakSlots", "missingSlots"):
        items = gap_report.get(key)
        if not isinstance(items, list):
            continue
        for item in items:
            if isinstance(item, dict) and str(item.get("slotId") or "") == slot_id:
                return dict(item)
    return None


def scene_requires_composition_author_brief(
    *,
    scene: dict[str, Any],
    slot: dict[str, Any],
    gap_item: dict[str, Any] | None,
) -> bool:
    source = str(scene.get("source") or "").strip()
    if source == "packaging_completion":
        return True
    role = normalize_slot_role(str(slot.get("role") or ""))
    if role in PACKAGING_ROLES:
        return True
    packaging_requirements = slot.get("packagingRequirements")
    if isinstance(packaging_requirements, list) and packaging_requirements:
        return True
    if isinstance(gap_item, dict):
        completion_mode = str(gap_item.get("completionMode") or "").strip()
        if completion_mode in _HF_COMPLETION_MODES:
            return True
        fixes = gap_item.get("suggestedFixes")
        if isinstance(fixes, list) and "hyperframes_material" in fixes:
            return True
    return False


def infer_composition_brief_mode(
    *,
    scene: dict[str, Any],
    slot: dict[str, Any],
    gap_item: dict[str, Any] | None,
) -> str:
    if isinstance(gap_item, dict):
        completion_mode = str(gap_item.get("completionMode") or "").strip()
        if completion_mode == "source_then_polish":
            return "source_then_polish"
        if completion_mode == "hf_native":
            return "hf_native"
        if completion_mode == "packaging_only":
            return "packaging_only"
        fixes = gap_item.get("suggestedFixes")
        if isinstance(fixes, list) and "hyperframes_material" in fixes:
            index = fixes.index("hyperframes_material")
            if index > 0:
                return "source_then_polish"
            if is_packaging_role(str(slot.get("role") or "")):
                return "hf_native"
            return "polish_only"
    source = str(scene.get("source") or "").strip()
    if source == "packaging_completion":
        return "hf_native"
    if is_packaging_role(str(slot.get("role") or "")):
        return "hf_native"
    return "polish_only"


def report_composition_brief_warnings(
    warnings: list[str],
    *,
    emit_event: Callable[..., Any] | None = None,
    emit_progress: Callable[[str, str], None] | None = None,
) -> None:
    """Surface compositionAuthorBrief validation/coercion issues on a dedicated task stage."""
    if not warnings:
        return
    message = "; ".join(dict.fromkeys(warnings))
    if emit_progress is not None:
        emit_progress("composition_brief_warning", message)
    elif emit_event is not None:
        emit_event(stage="composition_brief_warning", progress=0, message=message)


def infer_template_preference(slot: dict[str, Any]) -> str:
    role = normalize_slot_role(str(slot.get("role") or ""))
    return _TEMPLATE_BY_ROLE.get(role, "composition")


def normalize_composition_author_brief(
    raw: Any,
    *,
    scene: dict[str, Any],
    slot: dict[str, Any],
    gap_item: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError("compositionAuthorBrief must be an object")

    author_prompt = str(raw.get("authorPrompt") or "").strip()
    if not author_prompt:
        raise ValueError("compositionAuthorBrief.authorPrompt must be non-empty")
    if len(author_prompt) > _AUTHOR_PROMPT_MAX_LEN:
        author_prompt = author_prompt[:_AUTHOR_PROMPT_MAX_LEN]

    mode = str(raw.get("mode") or "").strip()
    if mode not in VALID_BRIEF_MODES:
        mode = infer_composition_brief_mode(scene=scene, slot=slot, gap_item=gap_item)

    layout_anchor = str(raw.get("layoutAnchor") or "").strip()
    if layout_anchor not in {"center", "lower_third", "upper_third"}:
        layout_anchor = infer_layout_anchor(mode=mode, slot=slot)
    else:
        inferred_anchor = infer_layout_anchor(mode=mode, slot=slot)
        if mode in {"hf_native", "packaging_only"} and layout_anchor != "center":
            layout_anchor = "center"
        elif mode in {"source_then_polish", "polish_only"} and layout_anchor == "center":
            layout_anchor = inferred_anchor

    if layout_anchor == "center":
        author_prompt = append_layout_hint_to_author_prompt(author_prompt, layout_anchor)

    brief: dict[str, Any] = {
        "mode": mode,
        "authorPrompt": author_prompt,
        "layoutAnchor": layout_anchor,
    }

    template = str(raw.get("templatePreference") or "").strip()
    if template in VALID_TEMPLATE_PREFERENCES:
        brief["templatePreference"] = template
    else:
        brief["templatePreference"] = infer_template_preference(slot)

    display_policy = raw.get("displayCopyPolicy")
    if isinstance(display_policy, dict):
        policy: dict[str, Any] = {}
        for key in ("allowed", "forbidden"):
            values = display_policy.get(key)
            if isinstance(values, list):
                cleaned = [str(item).strip() for item in values if str(item).strip()]
                if cleaned:
                    policy[key] = cleaned
        if policy:
            brief["displayCopyPolicy"] = policy

    validation = validate_contract("composition-author-brief", brief)
    if not validation.valid:
        raise ValueError(f"Invalid compositionAuthorBrief: {validation.errors}")
    return brief


def merge_display_copy_from_packaging(
    brief: dict[str, Any],
    packaging_overlay: dict[str, Any] | None,
) -> dict[str, Any]:
    if not isinstance(brief, dict):
        return brief
    if not isinstance(packaging_overlay, dict):
        return brief
    raw_allowed = packaging_overlay.get("displayCopy")
    if not isinstance(raw_allowed, list):
        return brief
    allowed = [str(item).strip() for item in raw_allowed if str(item).strip()]
    if not allowed:
        return brief
    merged = dict(brief)
    policy = dict(merged.get("displayCopyPolicy") or {})
    existing = [str(item).strip() for item in policy.get("allowed") or [] if str(item).strip()]
    seen = set(existing)
    for item in allowed:
        if item not in seen:
            existing.append(item)
            seen.add(item)
    policy["allowed"] = existing
    merged["displayCopyPolicy"] = policy
    return merged


def apply_composition_briefs_to_storyboard(
    storyboard: list[dict[str, Any]],
    *,
    structure: dict[str, Any],
    gap_report: dict[str, Any] | None,
    emit_warning: Callable[[str], None] | None = None,
) -> list[dict[str, Any]]:
    slots_by_id: dict[str, dict[str, Any]] = {}
    for slot in structure.get("slots") or []:
        if isinstance(slot, dict) and slot.get("id"):
            slots_by_id[str(slot["id"])] = slot

    mode = composition_brief_mode()
    updated: list[dict[str, Any]] = []

    for scene in storyboard:
        if not isinstance(scene, dict):
            updated.append(scene)
            continue
        item = dict(scene)
        slot_id = str(item.get("slotId") or "")
        slot = slots_by_id.get(slot_id, {})
        gap_item = gap_item_for_slot(gap_report, slot_id)
        required = scene_requires_composition_author_brief(
            scene=item,
            slot=slot,
            gap_item=gap_item,
        )
        raw_brief = item.get("compositionAuthorBrief")

        if raw_brief is None and not required:
            updated.append(item)
            continue

        if raw_brief is None and required:
            message = f"compositionAuthorBrief required for slot {slot_id}"
            if mode == "require":
                raise ValueError(message)
            if mode == "warn" and emit_warning is not None:
                emit_warning(message)
            updated.append(item)
            continue

        if raw_brief is not None:
            normalized = normalize_composition_author_brief(
                raw_brief,
                scene=item,
                slot=slot,
                gap_item=gap_item,
            )
            inferred = infer_composition_brief_mode(scene=item, slot=slot, gap_item=gap_item)
            if normalized and normalized.get("mode") != inferred:
                if emit_warning is not None:
                    emit_warning(
                        f"compositionAuthorBrief.mode realigned for slot {slot_id}: "
                        f"{normalized.get('mode')} -> {inferred}"
                    )
                normalized = {**normalized, "mode": inferred}
            item["compositionAuthorBrief"] = normalized

        updated.append(item)

    return updated
