from __future__ import annotations

import json
import re
from copy import deepcopy
from typing import Any


_PLACEHOLDER_TITLE = "{{title}}"
_PLACEHOLDER_SUBTITLE = "{{subtitle}}"


def _collect_storyboard_strings(scene: dict[str, Any]) -> list[tuple[str, str]]:
    """Return (literal, placeholder) pairs longest-first for replacement."""
    pairs: list[tuple[str, str]] = []
    script = str(scene.get("scriptIntent") or scene.get("script") or "").strip()
    visual = str(scene.get("visualIntent") or scene.get("visual") or "").strip()
    subtitle = str(scene.get("subtitle") or "").strip()
    on_screen = scene.get("onScreenText")
    if script:
        pairs.append((script, _PLACEHOLDER_TITLE))
    if subtitle:
        pairs.append((subtitle, _PLACEHOLDER_SUBTITLE))
    elif visual and visual != script:
        pairs.append((visual, _PLACEHOLDER_SUBTITLE))
    if isinstance(on_screen, list):
        for index, item in enumerate(on_screen[:5]):
            text = str(item).strip()
            if text:
                pairs.append((text, f"{{{{bullet{index + 1}}}}}"))
    elif isinstance(on_screen, str) and on_screen.strip():
        pairs.append((on_screen.strip(), "{{bullet1}}"))
    pairs.sort(key=lambda item: len(item[0]), reverse=True)
    return pairs


def _replace_in_text(text: str, pairs: list[tuple[str, str]]) -> str:
    updated = text
    for literal, placeholder in pairs:
        if len(literal) < 2:
            continue
        updated = updated.replace(literal, placeholder)
    return updated


def _strip_asset_urls(text: str) -> str:
    return re.sub(
        r"""(?:src|href)\s*=\s*['"][^'"]+['"]""",
        'src="{{assetUrl}}"',
        text,
        flags=re.IGNORECASE,
    )


def sanitize_instance_spec(
    spec: dict[str, Any],
    *,
    scene: dict[str, Any] | None,
    master_narration: str | None = None,
) -> dict[str, Any]:
    """Deterministic pre-LLM redaction of slot-specific literals."""
    sanitized = deepcopy(spec)
    pairs: list[tuple[str, str]] = []
    if scene:
        pairs.extend(_collect_storyboard_strings(scene))
    narration = (master_narration or "").strip()
    if narration and len(narration) >= 8:
        pairs.append((narration[:120], "{{narrationExcerpt}}"))
    pairs.sort(key=lambda item: len(item[0]), reverse=True)

    composition = sanitized.get("composition")
    if isinstance(composition, dict):
        for key in ("bodyHtml", "styles", "timelineScript"):
            raw = composition.get(key)
            if isinstance(raw, str) and raw.strip():
                composition[key] = _strip_asset_urls(_replace_in_text(raw, pairs))

    params = sanitized.get("params")
    if isinstance(params, dict):
        for key in ("title", "subtitle"):
            if isinstance(params.get(key), str):
                params[key] = _PLACEHOLDER_TITLE if key == "title" else _PLACEHOLDER_SUBTITLE
        bullets = params.get("bullets")
        if isinstance(bullets, list):
            params["bullets"] = [f"{{{{bullet{index + 1}}}}}" for index in range(len(bullets))]

    return sanitized


def storyboard_summary_for_slot(storyboard: list[dict[str, Any]], slot_id: str) -> str:
    for scene in storyboard:
        if str(scene.get("slotId", "")).strip() == slot_id:
            script = str(scene.get("scriptIntent") or scene.get("script") or "").strip()
            visual = str(scene.get("visualIntent") or scene.get("visual") or "").strip()
            parts = [part for part in (script, visual) if part]
            return " / ".join(parts)[:240]
    return ""


def find_storyboard_scene(storyboard: list[dict[str, Any]], slot_id: str) -> dict[str, Any] | None:
    for scene in storyboard:
        if str(scene.get("slotId", "")).strip() == slot_id:
            return scene
    return None


def load_generation_plan_context(
    storage_root,
    *,
    project_id: str,
    generation_id: str,
    slot_id: str,
) -> dict[str, Any]:
    from pathlib import Path

    plan_path = (
        Path(storage_root)
        / "projects"
        / project_id
        / "generations"
        / generation_id
        / "generation-plan.json"
    )
    if not plan_path.is_file():
        raise FileNotFoundError("generation-plan.json not found")
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    storyboard = plan.get("storyboard") if isinstance(plan.get("storyboard"), list) else []
    scene = find_storyboard_scene(storyboard, slot_id)
    action_id = None
    for action in plan.get("completionActions") or []:
        if not isinstance(action, dict):
            continue
        if str(action.get("slotId", "")).strip() != slot_id:
            continue
        provider = str(action.get("provider") or action.get("strategy") or "")
        if provider == "hyperframes_material":
            action_id = str(action.get("id") or "")
            break
    slot_role = str((scene or {}).get("role") or slot_id)
    return {
        "plan": plan,
        "scene": scene or {},
        "storyboardSummary": storyboard_summary_for_slot(storyboard, slot_id),
        "masterNarration": str(plan.get("masterNarration") or ""),
        "slotRole": slot_role,
        "actionId": action_id,
    }
