from __future__ import annotations

import re
from typing import Any, Literal

MaterialEditMode = Literal["edit", "full"]

_QUOTE_PATTERNS = (
    re.compile(r"「([^」]{2,})」"),
    re.compile(r"“([^”]{2,})”"),
    re.compile(r'"([^"]{2,})"'),
)
_CJK_SPLIT = re.compile(r"[，。；、]")
_FULL_REGEN_MARKERS = re.compile(
    r"重新生成|重新设计|核心文字|没有.*文字|请加.*文字|上屏.*文字|显示.*文字",
    re.IGNORECASE,
)
_MIN_CJK_LEN = 4


def _append_unique(items: list[str], seen: set[str], raw: str) -> None:
    text = str(raw or "").strip()
    if len(text) < 2 or text in seen:
        return
    seen.add(text)
    items.append(text)


def _split_script_phrases(script: str) -> list[str]:
    text = str(script or "").strip()
    if not text:
        return []
    parts = [chunk.strip() for chunk in _CJK_SPLIT.split(text) if chunk.strip()]
    phrases: list[str] = []
    seen: set[str] = set()
    if len(text) >= _MIN_CJK_LEN:
        _append_unique(phrases, seen, text)
    for part in parts:
        if len(part) >= _MIN_CJK_LEN:
            _append_unique(phrases, seen, part)
    return phrases


def _extract_quoted_phrases(text: str) -> list[str]:
    phrases: list[str] = []
    seen: set[str] = set()
    for pattern in _QUOTE_PATTERNS:
        for match in pattern.finditer(str(text or "")):
            _append_unique(phrases, seen, match.group(1))
    return phrases


def _existing_allowed_from_brief(finish_brief: dict[str, Any] | None) -> list[str]:
    if not isinstance(finish_brief, dict):
        return []
    render_policy = finish_brief.get("renderPolicy")
    if isinstance(render_policy, dict):
        allowed = render_policy.get("allowedDisplayCopy")
        if isinstance(allowed, list):
            cleaned = [str(item).strip() for item in allowed if str(item).strip()]
            if cleaned:
                return cleaned
    composition_brief = finish_brief.get("compositionAuthorBrief")
    if isinstance(composition_brief, dict):
        policy = composition_brief.get("displayCopyPolicy")
        if isinstance(policy, dict):
            allowed = policy.get("allowed")
            if isinstance(allowed, list):
                return [str(item).strip() for item in allowed if str(item).strip()]
    return []


def derive_allowed_display_copy(
    *,
    finish_brief: dict[str, Any] | None = None,
    edit_instruction: str = "",
    storyboard_scene: dict[str, Any] | None = None,
    composition_author_brief: dict[str, Any] | None = None,
) -> list[str]:
    allowed: list[str] = []
    seen: set[str] = set()

    for item in _existing_allowed_from_brief(finish_brief):
        _append_unique(allowed, seen, item)

    scene = storyboard_scene if isinstance(storyboard_scene, dict) else None
    if scene is None and isinstance(finish_brief, dict):
        nested = finish_brief.get("storyboardScene")
        scene = nested if isinstance(nested, dict) else None
    if scene is not None:
        for phrase in _split_script_phrases(str(scene.get("script") or "")):
            _append_unique(allowed, seen, phrase)

    cab = composition_author_brief
    if cab is None and isinstance(finish_brief, dict):
        nested = finish_brief.get("compositionAuthorBrief")
        cab = nested if isinstance(nested, dict) else None
    author_prompt = str((cab or {}).get("authorPrompt") or "")
    for phrase in _extract_quoted_phrases(author_prompt):
        _append_unique(allowed, seen, phrase)

    instruction = str(edit_instruction or "").strip()
    if instruction and _FULL_REGEN_MARKERS.search(instruction) and scene is not None:
        for phrase in _split_script_phrases(str(scene.get("script") or "")):
            _append_unique(allowed, seen, phrase)

    return allowed


def infer_material_edit_mode_for_gate_revise(
    edit_instruction: str,
    current_mode: str = "edit",
) -> MaterialEditMode:
    if str(current_mode or "").strip().lower() == "full":
        return "full"
    instruction = str(edit_instruction or "").strip()
    if instruction and _FULL_REGEN_MARKERS.search(instruction):
        return "full"
    return "edit"


def build_author_contract(
    *,
    allowed_display_copy: list[str],
    material_edit_mode: MaterialEditMode,
    must_change_spec: bool,
) -> dict[str, Any]:
    allowed = [str(item).strip() for item in allowed_display_copy if str(item).strip()]
    display_copy_mode = "allowed_list" if allowed else "text_free"
    return {
        "displayCopyMode": display_copy_mode,
        "allowedDisplayCopy": allowed,
        "materialEditMode": material_edit_mode,
        "mustChangeSpec": bool(must_change_spec),
    }


def apply_display_copy_to_finish_brief(
    finish_brief: dict[str, Any],
    *,
    edit_instruction: str = "",
    storyboard_scene: dict[str, Any] | None = None,
) -> dict[str, Any]:
    brief = dict(finish_brief)
    composition_brief = brief.get("compositionAuthorBrief")
    cab = composition_brief if isinstance(composition_brief, dict) else None
    allowed = derive_allowed_display_copy(
        finish_brief=brief,
        edit_instruction=edit_instruction,
        storyboard_scene=storyboard_scene,
        composition_author_brief=cab,
    )
    render_policy = dict(brief.get("renderPolicy") or {})
    if allowed:
        render_policy["allowedDisplayCopy"] = allowed
        render_policy["displayCopyMode"] = "allowed_list"
    else:
        render_policy.setdefault("allowedDisplayCopy", [])
        render_policy.setdefault("displayCopyMode", "text_free")
    render_policy.setdefault("forbidVoiceoverText", True)
    render_policy.setdefault("forbidBriefVerbatim", True)
    brief["renderPolicy"] = render_policy
    return brief
