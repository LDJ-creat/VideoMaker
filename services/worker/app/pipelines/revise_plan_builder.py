from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from app.pipelines.intent_applier import build_source_summary, parse_edit_intent_for_api

MAX_SESSION_TURNS = 5
SCRIPT_PREVIEW_LEN = 80


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
            elif operation in {"adjust_hook", "reorder_selling_points", "change_pace", "adjust_cta"}:
                tools.append("storyboard_agent")
            elif operation == "change_packaging_style":
                tools.append("packaging_agent")
            else:
                tools.append("full_pipeline")

    unique_tools = list(dict.fromkeys(tools))
    patch_only = unique_tools and all(t in {"subtitle_patch", "timeline_scene_patch"} for t in unique_tools)
    if patch_only and len(unique_tools) == 1 and unique_tools[0] == "subtitle_patch":
        steps = [{"tool": "subtitle_patch", "description": "调整字幕密度并重建字幕轨"}]
        return "low", "in_place", True, steps
    if patch_only and unique_tools == ["timeline_scene_patch"]:
        steps = [{"tool": "timeline_scene_patch", "description": "调整分镜时长并重建时间线"}]
        return "low", "in_place", True, steps
    if patch_only:
        steps = [{"tool": t, "description": t} for t in unique_tools]
        return "low", "in_place", True, steps

    if any(t in {"material_regen", "full_pipeline"} for t in unique_tools):
        steps = [{"tool": t, "description": t} for t in unique_tools]
        return "high", "fork", True, steps
    steps = [{"tool": t, "description": t} for t in unique_tools]
    return "medium", "fork", True, steps


def build_planner_output_from_rules(
    instruction: str,
    source_plan: dict[str, Any],
) -> dict[str, Any]:
    source_summary = build_source_summary(source_plan)
    payload = parse_edit_intent_for_api(instruction, source_summary)
    intents = list(payload.get("intents") or [])
    cost_tier, execution_mode, requires_render, steps = _infer_execution_from_intents(intents)
    summaries: list[str] = [str(i.get("rationale") or "") for i in intents if i.get("rationale")]
    summary = "；".join(summaries) if summaries else instruction
    return {
        "summary": summary,
        "costTier": cost_tier,
        "requiresFullRender": requires_render,
        "executionMode": execution_mode,
        "intents": intents,
        "executionSteps": steps,
        "conversationSummary": summary,
    }


def enrich_revise_plan(
    planner_output: dict[str, Any],
    *,
    source_generation_id: str,
    instruction: str,
    session_id: str,
    turn_id: str | None = None,
) -> dict[str, Any]:
    plan_id = str(uuid.uuid4())
    resolved_turn_id = turn_id or str(uuid.uuid4())
    affected: list[str] = []
    for intent in planner_output.get("intents") or []:
        if not isinstance(intent, dict):
            continue
        scene_ids = intent.get("sceneIds")
        if isinstance(scene_ids, list):
            affected.extend(str(s) for s in scene_ids if s)
    if isinstance(planner_output.get("affectedSceneIds"), list):
        affected.extend(str(s) for s in planner_output["affectedSceneIds"] if s)

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
        "intents": list(planner_output.get("intents") or []),
        "executionSteps": list(planner_output.get("executionSteps") or []),
        "status": "draft",
        "createdAt": _utc_now_iso(),
    }
    if affected:
        plan["affectedSceneIds"] = list(dict.fromkeys(affected))
    return plan
