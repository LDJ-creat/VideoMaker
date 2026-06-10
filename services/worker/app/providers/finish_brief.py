from __future__ import annotations

from typing import Any

_DEFAULT_CONSTRAINTS = (
    "do_not_replace_base_media",
    "keep_base_video_visible",
    "never_render_voiceover_text",
)

_REQUIREMENT_TASK_MAP: dict[str, str] = {
    "caption": "subtitle_motion_only",
    "captions": "subtitle_motion_only",
    "subtitle": "subtitle_motion_only",
    "subtitles": "subtitle_motion_only",
    "lower_third": "lower_third_motion",
    "lower third": "lower_third_motion",
    "lower-third": "lower_third_motion",
    "title_card": "title_card_motion",
    "title card": "title_card_motion",
    "price_tag": "price_tag_motion",
    "cta": "cta_motion",
    "sticker": "sticker_motion",
    "overlay": "overlay_motion",
}


def _scene_for_slot(slot_id: str, storyboard: list[dict[str, Any]]) -> dict[str, Any] | None:
    for scene in storyboard:
        if isinstance(scene, dict) and scene.get("slotId") == slot_id:
            return scene
    return None


def _packaging_overlay_for_slot(
    slot_id: str,
    packaging_plan: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not isinstance(packaging_plan, dict):
        return None
    overlays = packaging_plan.get("slotOverlays") or packaging_plan.get("overlays")
    if not isinstance(overlays, list):
        return None
    for item in overlays:
        if isinstance(item, dict) and item.get("slotId") == slot_id:
            return dict(item)
    return None


def _derive_polish_tasks(
    *,
    packaging_requirements: list[Any],
    finish_intent: str,
) -> list[str]:
    tasks: list[str] = []
    seen: set[str] = set()

    def add(task: str) -> None:
        if task and task not in seen:
            seen.add(task)
            tasks.append(task)

    for raw in packaging_requirements:
        token = str(raw or "").strip().lower().replace("-", "_")
        if not token:
            continue
        mapped = _REQUIREMENT_TASK_MAP.get(token) or _REQUIREMENT_TASK_MAP.get(token.replace("_", " "))
        add(mapped or f"packaging_{token}")

    intent_lower = finish_intent.lower()
    if any(key in intent_lower for key in ("字幕", "caption", "subtitle")):
        add("subtitle_motion_only")
    if any(key in intent_lower for key in ("lower third", "lower_third", "标题条")):
        add("lower_third_motion")
    if any(key in intent_lower for key in ("角标", "sticker", "花字")):
        add("sticker_motion")
    if any(key in intent_lower for key in ("卡片", "card", "benefit")):
        add("card_motion")
    return tasks


def _allowed_display_copy(overlay: dict[str, Any] | None) -> list[str]:
    if not isinstance(overlay, dict):
        return []
    raw = overlay.get("displayCopy")
    if not isinstance(raw, list):
        return []
    return [str(item).strip() for item in raw if str(item).strip()]


def _merge_constraints(existing: list[Any] | None) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for item in list(existing or []) + list(_DEFAULT_CONSTRAINTS):
        token = str(item or "").strip()
        if token and token not in seen:
            seen.add(token)
            merged.append(token)
    return merged


def _enrich_semantic_fields(
    brief: dict[str, Any],
    *,
    slot: dict[str, Any],
    storyboard_scene: dict[str, Any] | None,
    packaging_overlay: dict[str, Any] | None,
) -> dict[str, Any]:
    visual = str((storyboard_scene or {}).get("visual") or "").strip()
    script_line = str((storyboard_scene or {}).get("script") or "").strip()
    narrative_goal = str(slot.get("scriptIntent") or slot.get("visualIntent") or "").strip()
    finish_intent = str(brief.get("finishIntent") or "").strip()
    packaging_requirements = list(brief.get("packagingRequirements") or slot.get("packagingRequirements") or [])

    creative = dict(brief.get("creativeBrief") or {})
    if visual and not creative.get("visualDirection"):
        creative["visualDirection"] = visual
    if narrative_goal and not creative.get("narrativeGoal"):
        creative["narrativeGoal"] = narrative_goal
    polish_tasks = creative.get("polishTasks")
    if not isinstance(polish_tasks, list) or not polish_tasks:
        creative["polishTasks"] = _derive_polish_tasks(
            packaging_requirements=packaging_requirements,
            finish_intent=finish_intent,
        )
    if creative:
        brief["creativeBrief"] = creative

    voiceover = dict(brief.get("voiceoverContext") or {})
    if script_line and not voiceover.get("line"):
        voiceover["line"] = script_line
    voiceover["doNotRender"] = True
    if voiceover.get("line") or voiceover.get("doNotRender"):
        brief["voiceoverContext"] = voiceover

    render_policy = dict(brief.get("renderPolicy") or {})
    render_policy.setdefault("forbidVoiceoverText", True)
    render_policy.setdefault("forbidBriefVerbatim", True)
    allowed = render_policy.get("allowedDisplayCopy")
    if not isinstance(allowed, list) or not allowed:
        render_policy["allowedDisplayCopy"] = _allowed_display_copy(packaging_overlay)
    brief["renderPolicy"] = render_policy

    if storyboard_scene and "storyboardScene" not in brief:
        brief["storyboardScene"] = {
            "script": script_line,
            "visual": visual,
        }

    brief["constraints"] = _merge_constraints(brief.get("constraints") if isinstance(brief.get("constraints"), list) else None)
    return brief


def build_finish_brief(
    *,
    gap_item: dict[str, Any],
    slot: dict[str, Any],
    storyboard_scene: dict[str, Any] | None,
    base_media: dict[str, Any] | None,
    packaging_plan: dict[str, Any] | None = None,
    source_provider: str | None = None,
    duration_sec: float | None = None,
) -> dict[str, Any]:
    completion_mode = str(gap_item.get("completionMode") or "source_only")
    finish_intent = str(gap_item.get("finishIntent") or "").strip()
    packaging_requirements = list(slot.get("packagingRequirements") or [])
    packaging_hint = str(slot.get("packagingHint") or "").strip()

    overlay = _packaging_overlay_for_slot(str(slot.get("id", "")), packaging_plan)

    brief: dict[str, Any] = {
        "completionMode": completion_mode,
        "constraints": list(_DEFAULT_CONSTRAINTS),
    }
    if finish_intent:
        brief["finishIntent"] = finish_intent
    if packaging_requirements:
        brief["packagingRequirements"] = packaging_requirements
    if packaging_hint:
        brief["packagingHint"] = packaging_hint
    if base_media:
        brief["baseMedia"] = dict(base_media)
    if source_provider:
        brief["sourceProvider"] = source_provider
    if duration_sec is not None and duration_sec > 0:
        brief["durationSec"] = round(float(duration_sec), 2)
    if overlay:
        brief["packagingOverlay"] = overlay

    return _enrich_semantic_fields(
        brief,
        slot=slot,
        storyboard_scene=storyboard_scene,
        packaging_overlay=overlay,
    )


def build_finish_brief_for_action(
    *,
    action: dict[str, Any],
    slot: dict[str, Any],
    storyboard: list[dict[str, Any]],
    gap_item: dict[str, Any] | None,
    base_media: dict[str, Any] | None,
    packaging_plan: dict[str, Any] | None,
    source_provider: str | None,
    duration_sec: float | None,
) -> dict[str, Any]:
    gap = gap_item or {}
    scene = _scene_for_slot(str(action.get("slotId", "")), storyboard)
    overlay = _packaging_overlay_for_slot(str(slot.get("id", "")), packaging_plan)

    if isinstance(action.get("finishBrief"), dict):
        brief = dict(action["finishBrief"])
    else:
        brief = build_finish_brief(
            gap_item=gap,
            slot=slot,
            storyboard_scene=scene,
            base_media=base_media,
            packaging_plan=packaging_plan,
            source_provider=source_provider,
            duration_sec=duration_sec,
        )

    if base_media and "baseMedia" not in brief:
        brief["baseMedia"] = dict(base_media)
    if source_provider:
        brief["sourceProvider"] = source_provider

    return _enrich_semantic_fields(
        brief,
        slot=slot,
        storyboard_scene=scene,
        packaging_overlay=overlay or brief.get("packagingOverlay") if isinstance(brief.get("packagingOverlay"), dict) else overlay,
    )
