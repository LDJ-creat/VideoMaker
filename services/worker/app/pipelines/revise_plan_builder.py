from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from app.pipelines.intent_applier import build_source_summary, parse_edit_intent_for_api
from app.pipelines.revise_scope import resolve_affected_scene_ids, resolve_slot_ids_from_intents

MAX_SESSION_TURNS = 5
SCRIPT_PREVIEW_LEN = 80

_SCENE_MARKERS = ("最后一镜", "最后一段", "最后一段", "最后一镜", "最后一幕", "第", "镜")
_VISUAL_PACKAGING_MARKERS = ("画面", "合成", "hf", "素材", "镜头", "重生成", "换画面")
_OVERLAY_PACKAGING_MARKERS = ("标题卡", "字幕", "转场", "overlay", "包装样式", "包装风格")


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def build_storyboard_scenes_for_planner(source_plan: dict[str, Any]) -> list[dict[str, Any]]:
    storyboard = source_plan.get("storyboard") if isinstance(source_plan.get("storyboard"), list) else []
    scenes: list[dict[str, Any]] = []
    for scene in storyboard:
        if not isinstance(scene, dict):
            continue
        script = str(scene.get("script") or "")
        preview = script[:SCRIPT_PREVIEW_LEN]
        if len(script) > SCRIPT_PREVIEW_LEN:
            preview += "…"
        scenes.append(
            {
                "id": str(scene.get("id") or ""),
                "slotId": str(scene.get("slotId") or ""),
                "startSec": float(scene.get("startSec", 0.0) or 0.0),
                "endSec": float(scene.get("endSec", 0.0) or 0.0),
                "scriptPreview": preview,
            }
        )
    return scenes


def build_session_turns_for_planner(session: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(session, dict):
        return []
    turns = session.get("turns")
    if not isinstance(turns, list):
        return []
    recent = turns[-MAX_SESSION_TURNS:]
    payload: list[dict[str, Any]] = []
    for turn in recent:
        if not isinstance(turn, dict):
            continue
        item: dict[str, Any] = {
            "instruction": str(turn.get("instruction") or ""),
            "status": str(turn.get("status") or "planned"),
        }
        if turn.get("planSummary"):
            item["planSummary"] = str(turn["planSummary"])
        payload.append(item)
    return payload


def _resolve_target_scene(instruction: str, source_plan: dict[str, Any]) -> dict[str, Any] | None:
    storyboard = [
        scene for scene in (source_plan.get("storyboard") or []) if isinstance(scene, dict)
    ]
    if not storyboard:
        return None
    text = instruction.strip().lower()
    if "最后一镜" in instruction or "最后一幕" in instruction or "最后一段" in instruction:
        return storyboard[-1]
    if "开头" in instruction or "第一镜" in instruction:
        return storyboard[0]
    for index, scene in enumerate(storyboard, start=1):
        if f"第{index}镜" in instruction:
            return scene
    _ = text
    return None


_STORYBOARD_ROUTING_OPERATIONS = frozenset(
    {"adjust_hook", "reorder_selling_points", "change_pace", "adjust_cta"}
)
_STORYBOARD_ROUTING_TOOLS = frozenset(
    {"storyboard_agent", "full_pipeline", "script_revise", "material_regen"}
)


def _has_non_packaging_storyboard_intent(intents: list[dict[str, Any]]) -> bool:
    for intent in intents:
        operation = str(intent.get("operation", ""))
        tool = str(intent.get("executionTool") or "")
        if operation in _STORYBOARD_ROUTING_OPERATIONS:
            return True
        if tool in _STORYBOARD_ROUTING_TOOLS:
            return True
    return False


def _can_rewrite_whole_request_to_scene_route(intents: list[dict[str, Any]]) -> bool:
    """Only collapse the full request when it is a single packaging/scene edit."""
    if len(intents) > 1:
        return False
    if _has_non_packaging_storyboard_intent(intents):
        return False
    return True


def route_packaging_intents(instruction: str, intents: list[dict[str, Any]], source_plan: dict[str, Any]) -> list[dict[str, Any]]:
    """Rewrite generic packaging intents into scoped low-cost routes when possible."""
    target_scene = _resolve_target_scene(instruction, source_plan)
    text = instruction.lower()
    visual = any(marker in instruction or marker in text for marker in _VISUAL_PACKAGING_MARKERS)
    overlay = any(marker in instruction or marker in text for marker in _OVERLAY_PACKAGING_MARKERS)

    if (
        _can_rewrite_whole_request_to_scene_route(intents)
        and target_scene is not None
        and (visual or overlay or "背景" in instruction or "包装" in instruction)
    ):
        scene_id = str(target_scene.get("id") or "")
        slot_id = str(target_scene.get("slotId") or "")
        if visual and ("背景" in instruction or "包装" in instruction or "画面" in instruction):
            return [
                {
                    "target": "generation_plan.storyboard",
                    "operation": "change_packaging_style",
                    "params": {
                        "requiresMaterialRegen": True,
                        "sceneId": scene_id,
                        "style": "updated",
                    },
                    "rationale": "单镜画面/合成背景需要重生成素材",
                    "scope": "scene",
                    "sceneIds": [scene_id] if scene_id else [],
                    "slotIds": [slot_id] if slot_id else [],
                    "executionTool": "material_regen",
                }
            ]
        return [
            {
                "target": "generation_plan.packaging",
                "operation": "packaging_scene_patch",
                "params": {
                    "sceneId": scene_id,
                    "backgroundPreset": "dark" if "深" in instruction else "scene-overlay",
                },
                "rationale": "单镜时间线层包装就地更新",
                "scope": "scene",
                "sceneIds": [scene_id] if scene_id else [],
                "slotIds": [slot_id] if slot_id else [],
                "executionTool": "packaging_scene_patch",
            }
        ]

    if not intents:
        return intents

    routed: list[dict[str, Any]] = []
    for intent in intents:
        operation = str(intent.get("operation", ""))
        if operation == "change_packaging_style" and target_scene is not None:
            intent = {
                **intent,
                "executionTool": "packaging_agent",
            }
        routed.append(intent)
    return routed


def _infer_execution_from_intents(intents: list[dict[str, Any]]) -> tuple[str, str, bool, list[dict[str, Any]]]:
    tools: list[str] = []
    for intent in intents:
        tool = intent.get("executionTool")
        if isinstance(tool, str) and tool:
            tools.append(tool)
        else:
            operation = str(intent.get("operation", ""))
            if operation in {"reduce_subtitles", "increase_subtitles", "subtitle_patch"}:
                tools.append("subtitle_patch")
            elif operation == "timeline_scene_patch":
                tools.append("timeline_scene_patch")
            elif operation == "packaging_scene_patch":
                tools.append("packaging_scene_patch")
            elif operation in {"adjust_hook", "reorder_selling_points", "change_pace", "adjust_cta"}:
                tools.append("storyboard_agent")
            elif operation == "change_packaging_style":
                tools.append("packaging_agent")
            else:
                tools.append("full_pipeline")

    unique_tools = list(dict.fromkeys(tools))
    patch_only = unique_tools and all(
        t in {"subtitle_patch", "timeline_scene_patch", "packaging_scene_patch"} for t in unique_tools
    )
    if patch_only and len(unique_tools) == 1 and unique_tools[0] == "subtitle_patch":
        steps = [{"tool": "subtitle_patch", "description": "调整字幕密度并重建字幕轨"}]
        return "low", "in_place", True, steps
    if patch_only and unique_tools == ["timeline_scene_patch"]:
        steps = [{"tool": "timeline_scene_patch", "description": "调整分镜时长并重建时间线"}]
        return "low", "in_place", True, steps
    if patch_only and unique_tools == ["packaging_scene_patch"]:
        steps = [{"tool": "packaging_scene_patch", "description": "就地更新单镜包装 overlay 并重建时间线"}]
        return "low", "in_place", True, steps
    if patch_only:
        steps = [{"tool": t, "description": t} for t in unique_tools]
        return "low", "in_place", True, steps

    if any(t in {"material_regen", "full_pipeline"} for t in unique_tools):
        steps = [{"tool": t, "description": t} for t in unique_tools]
        cost = "high" if "full_pipeline" in unique_tools else "medium"
        return cost, "fork", True, steps
    steps = [{"tool": t, "description": t} for t in unique_tools]
    return "medium", "fork", True, steps


def build_planner_output_from_intents(
    intents: list[dict[str, Any]],
    instruction: str,
    *,
    source_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cost_tier, execution_mode, requires_render, steps = _infer_execution_from_intents(intents)
    summaries: list[str] = [str(i.get("rationale") or "") for i in intents if i.get("rationale")]
    summary = "；".join(summaries) if summaries else instruction
    affected_scene_ids = resolve_affected_scene_ids(intents)
    storyboard = (
        list(source_plan.get("storyboard") or [])
        if isinstance(source_plan, dict) and isinstance(source_plan.get("storyboard"), list)
        else []
    )
    affected_slot_ids = resolve_slot_ids_from_intents(intents, storyboard=storyboard)
    output: dict[str, Any] = {
        "summary": summary,
        "costTier": cost_tier,
        "requiresFullRender": requires_render,
        "executionMode": execution_mode,
        "intents": intents,
        "executionSteps": steps,
        "conversationSummary": summary,
    }
    if affected_scene_ids:
        output["affectedSceneIds"] = affected_scene_ids
    if affected_slot_ids:
        output["affectedSlotIds"] = affected_slot_ids
    return output


def build_planner_output_from_rules(
    instruction: str,
    source_plan: dict[str, Any],
) -> dict[str, Any]:
    source_summary = build_source_summary(source_plan)
    try:
        payload = parse_edit_intent_for_api(instruction, source_summary)
        intents = list(payload.get("intents") or [])
    except ValueError:
        intents = []
    intents = route_packaging_intents(instruction, intents, source_plan)
    if not intents:
        raise ValueError("Could not parse any edit intents from instruction")
    return build_planner_output_from_intents(intents, instruction, source_plan=source_plan)


def enrich_revise_plan(
    planner_output: dict[str, Any],
    *,
    source_generation_id: str,
    instruction: str,
    session_id: str,
    turn_id: str | None = None,
    source_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    plan_id = str(uuid.uuid4())
    resolved_turn_id = turn_id or str(uuid.uuid4())
    intents = [intent for intent in (planner_output.get("intents") or []) if isinstance(intent, dict)]
    storyboard = (
        list(source_plan.get("storyboard") or [])
        if isinstance(source_plan, dict) and isinstance(source_plan.get("storyboard"), list)
        else []
    )
    affected_scenes = resolve_affected_scene_ids(intents)
    if isinstance(planner_output.get("affectedSceneIds"), list):
        affected_scenes = list(dict.fromkeys([*affected_scenes, *(str(s) for s in planner_output["affectedSceneIds"] if s)]))
    affected_slots = resolve_slot_ids_from_intents(intents, storyboard=storyboard)

    plan: dict[str, Any] = {
        "planId": plan_id,
        "sessionId": session_id,
        "turnId": resolved_turn_id,
        "sourceGenerationId": source_generation_id,
        "instruction": instruction,
        "summary": str(planner_output.get("summary") or instruction),
        "costTier": planner_output.get("costTier", "medium"),
        "requiresFullRender": bool(planner_output.get("requiresFullRender", True)),
        "executionMode": planner_output.get("executionMode", "fork"),
        "intents": intents,
        "executionSteps": list(planner_output.get("executionSteps") or []),
        "status": "draft",
        "createdAt": _utc_now_iso(),
    }
    if affected_scenes:
        plan["affectedSceneIds"] = affected_scenes
    if affected_slots:
        plan["affectedSlotIds"] = affected_slots
    return plan
