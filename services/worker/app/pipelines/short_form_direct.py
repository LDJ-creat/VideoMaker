from __future__ import annotations

from typing import Any

from app.gateway.model_gateway import ModelGateway
from app.pipelines.generation_strategy import short_form_video_gen_enabled
from app.providers.completion_registry import filter_aigc_completion_actions
from app.tools.image_gen_tool import ToolError


def _action_strategy(action: dict[str, Any]) -> str:
    return str(action.get("strategy") or action.get("provider") or "")


def short_form_plan_requires_video(plan: dict[str, Any]) -> bool:
    if not short_form_video_gen_enabled():
        return False
    actions = filter_aigc_completion_actions(list(plan.get("completionActions") or []))
    return any(_action_strategy(action) == "video_generation" for action in actions)


def validate_short_form_material_gateway(
    *,
    gateway: Any,
    plan: dict[str, Any],
) -> None:
    """Fail fast when short-form direct needs video but no live video provider is configured."""
    if not short_form_plan_requires_video(plan):
        return
    if getattr(gateway, "is_fixture", False):
        return
    if not isinstance(gateway, ModelGateway):
        raise ToolError(
            code="video_provider_not_configured",
            message=(
                "Short-form generation (≤60s) requires a configured video provider. "
                "Configure Model Gateway video settings or increase target duration."
            ),
            retryable=False,
        )
    video = gateway.config.video
    if not str(video.api_key or "").strip() or not str(video.base_url or "").strip():
        raise ToolError(
            code="video_provider_not_configured",
            message=(
                "Short-form generation requires video provider baseUrl and API key. "
                "Configure Model Gateway video settings in the workbench."
            ),
            retryable=False,
        )


def simplify_storyboard_for_short_form(
    storyboard: list[dict[str, Any]],
    *,
    target_sec: float,
    max_scenes: int = 3,
) -> list[dict[str, Any]]:
    if not storyboard:
        return []
    if len(storyboard) <= max_scenes:
        return [dict(scene) for scene in storyboard]

    sorted_scenes = sorted(storyboard, key=lambda item: float(item.get("startSec", 0.0)))
    chunk_size = max(1, (len(sorted_scenes) + max_scenes - 1) // max_scenes)
    merged: list[dict[str, Any]] = []
    cursor = 0.0
    slot_duration = max(0.5, float(target_sec) / max_scenes)

    for index in range(max_scenes):
        start = index * chunk_size
        end = min(len(sorted_scenes), start + chunk_size)
        if start >= end:
            break
        group = sorted_scenes[start:end]
        first = dict(group[0])
        scripts = [str(item.get("script") or "").strip() for item in group if str(item.get("script") or "").strip()]
        visuals = [str(item.get("visual") or "").strip() for item in group if str(item.get("visual") or "").strip()]
        scene_end = cursor + slot_duration
        merged.append(
            {
                "id": str(first.get("id") or f"scene-short-{index + 1}"),
                "slotId": str(first.get("slotId") or f"slot-short-{index + 1}"),
                "startSec": round(cursor, 3),
                "endSec": round(scene_end, 3),
                "visual": " / ".join(visuals[:2]) if visuals else str(first.get("visual") or ""),
                "script": " ".join(scripts),
                "source": str(first.get("source") or "generated"),
            }
        )
        cursor = scene_end

    if merged:
        merged[-1]["endSec"] = round(float(target_sec), 3)
    return merged


def filter_short_form_completion_actions(
    actions: list[dict[str, Any]],
    *,
    primary_slot_id: str,
) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    video_added = False
    for action in actions:
        if not isinstance(action, dict):
            continue
        strategy = _action_strategy(action)
        slot_id = str(action.get("slotId") or "")
        if strategy == "video_generation":
            if video_added:
                continue
            if slot_id and slot_id != primary_slot_id:
                action = dict(action)
                action["slotId"] = primary_slot_id
            filtered.append(action)
            video_added = True
            continue
        if video_added and strategy in {"image_generation", "hyperframes_material"}:
            continue
        if strategy in {"tts", "hyperframes_material", "image_generation", "asset_reuse", "text_completion"}:
            filtered.append(dict(action))
    return filtered
