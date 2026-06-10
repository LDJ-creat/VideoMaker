from __future__ import annotations

import json
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from app.pipelines.generation_pipeline import (
    merge_scene_overlays_into_timeline,
    merge_script_subtitles_into_timeline,
)
from app.pipelines.generation_pipeline import _build_timeline  # noqa: PLC2701
from app.pipelines.revise_scope import resolve_slot_ids_from_intents
from app.pipelines.tts_mode import global_tts_eligible, resolve_tts_mode
from app.render.backend import RenderOptions
from app.render.resolve_render_backend import build_render_backend
from app.runtime.checkpoint import generation_artifact_root
from app.tools.ffmpeg_tool import build_fixture_ffmpeg_tool

EmitFn = Callable[..., dict[str, Any]]
SUBTITLE_CLIP_PREFIX = "subtitle-"


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def _write_snapshot(generation_root: Path, plan: dict[str, Any]) -> None:
    snapshot: dict[str, Any] = {}
    if isinstance(plan.get("storyboard"), list):
        snapshot["storyboard"] = plan["storyboard"]
    if isinstance(plan.get("masterNarration"), str):
        snapshot["masterNarration"] = plan["masterNarration"]
    if isinstance(plan.get("packagingPlan"), dict):
        snapshot["packagingPlan"] = plan["packagingPlan"]
    if snapshot:
        (generation_root / "revise-snapshot.json").write_text(
            json.dumps(snapshot, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )


def _strip_subtitle_clips(timeline: dict[str, Any], slot_ids: set[str] | None = None) -> dict[str, Any]:
    tracks = timeline.get("tracks")
    if not isinstance(tracks, list):
        return timeline
    for track in tracks:
        if not isinstance(track, dict) or track.get("type") != "text":
            continue
        clips = track.get("clips")
        if not isinstance(clips, list):
            continue
        filtered: list[dict[str, Any]] = []
        for clip in clips:
            if not isinstance(clip, dict):
                continue
            clip_id = str(clip.get("id", ""))
            if not clip_id.startswith(SUBTITLE_CLIP_PREFIX):
                filtered.append(clip)
                continue
            if slot_ids is None:
                continue
            remainder = clip_id[len(SUBTITLE_CLIP_PREFIX):]
            slot_part = remainder.split("-", 1)[0]
            if slot_part not in slot_ids:
                filtered.append(clip)
        track["clips"] = filtered
    return timeline


def _apply_subtitle_density(packaging_plan: dict[str, Any], intents: list[dict[str, Any]]) -> dict[str, Any]:
    packaging = dict(packaging_plan)
    subtitle = dict(packaging.get("subtitle") or {})
    for intent in intents:
        operation = str(intent.get("operation", ""))
        params = intent.get("params") if isinstance(intent.get("params"), dict) else {}
        if operation in {"reduce_subtitles", "subtitle_patch"} and params.get("density") == "high":
            subtitle["density"] = "high"
        elif operation in {"reduce_subtitles", "subtitle_patch"}:
            subtitle["density"] = "low"
        elif operation == "increase_subtitles":
            subtitle["density"] = "high"
    packaging["subtitle"] = subtitle
    packaging["visualDensity"] = subtitle.get("density") or packaging.get("visualDensity")
    return packaging


def _collect_remove_slot_ids(intents: list[dict[str, Any]]) -> set[str]:
    slot_ids: set[str] = set()
    for intent in intents:
        if str(intent.get("operation", "")) != "subtitle_patch":
            continue
        params = intent.get("params") if isinstance(intent.get("params"), dict) else {}
        if params.get("remove") or params.get("clear"):
            scene_ids = intent.get("sceneIds") if isinstance(intent.get("sceneIds"), list) else []
            slot_ids_from_params = params.get("slotIds") if isinstance(params.get("slotIds"), list) else []
            for sid in slot_ids_from_params:
                slot_ids.add(str(sid))
            for sid in scene_ids:
                slot_ids.add(str(sid))
    return slot_ids


def apply_subtitle_patch(plan: dict[str, Any], intents: list[dict[str, Any]]) -> dict[str, Any]:
    updated = dict(plan)
    packaging = _apply_subtitle_density(
        updated.get("packagingPlan") if isinstance(updated.get("packagingPlan"), dict) else {},
        intents,
    )
    updated["packagingPlan"] = packaging
    storyboard = list(updated.get("storyboard") or [])
    timeline = dict(updated.get("timeline") or {"tracks": []})
    remove_slots = _collect_remove_slot_ids(intents)
    if remove_slots:
        for scene in storyboard:
            if isinstance(scene, dict) and str(scene.get("slotId", "")) in remove_slots:
                scene["script"] = ""
        timeline = _strip_subtitle_clips(timeline, remove_slots)
    else:
        timeline = _strip_subtitle_clips(timeline, None)
    tts_mode = resolve_tts_mode(updated)
    timeline = merge_script_subtitles_into_timeline(
        timeline,
        storyboard,
        packaging,
        skip_subtitles=global_tts_eligible(updated, mode=tts_mode),
    )
    duration = max((float(s.get("endSec", 0)) for s in storyboard if isinstance(s, dict)), default=0.0)
    timeline["durationSec"] = duration
    updated["storyboard"] = storyboard
    updated["timeline"] = timeline
    return updated


def _find_scene_index(storyboard: list[dict[str, Any]], scene_id: str, slot_id: str) -> int | None:
    for index, scene in enumerate(storyboard):
        if not isinstance(scene, dict):
            continue
        if scene_id and str(scene.get("id", "")) == scene_id:
            return index
        if slot_id and str(scene.get("slotId", "")) == slot_id:
            return index
    return None


def apply_timeline_scene_patch(plan: dict[str, Any], intents: list[dict[str, Any]]) -> dict[str, Any]:
    updated = dict(plan)
    storyboard = [dict(s) for s in updated.get("storyboard") or [] if isinstance(s, dict)]
    for intent in intents:
        if str(intent.get("operation", "")) != "timeline_scene_patch":
            continue
        params = intent.get("params") if isinstance(intent.get("params"), dict) else {}
        scene_id = str(params.get("sceneId") or "")
        slot_id = str(params.get("slotId") or "")
        index = _find_scene_index(storyboard, scene_id, slot_id)
        if index is None:
            continue
        scene = storyboard[index]
        old_end = float(scene.get("endSec", 0))
        delta = params.get("deltaSec")
        new_end = params.get("newEndSec")
        if new_end is not None:
            scene["endSec"] = round(float(new_end), 3)
        elif delta is not None:
            scene["endSec"] = round(float(scene.get("startSec", 0)) + float(delta), 3)
        min_duration = float(params.get("minDurationSec", 0.5))
        if float(scene["endSec"]) - float(scene.get("startSec", 0)) < min_duration:
            scene["endSec"] = round(float(scene.get("startSec", 0)) + min_duration, 3)
        ripple = bool(params.get("ripple", True))
        if ripple:
            shift = float(scene["endSec"]) - old_end
            if shift != 0:
                for downstream in storyboard[index + 1:]:
                    downstream["startSec"] = round(float(downstream.get("startSec", 0)) + shift, 3)
                    downstream["endSec"] = round(float(downstream.get("endSec", 0)) + shift, 3)
        storyboard[index] = scene
    updated["storyboard"] = storyboard
    return updated


def _resolve_scene_target(
    storyboard: list[dict[str, Any]],
    intent: dict[str, Any],
) -> dict[str, Any] | None:
    params = intent.get("params") if isinstance(intent.get("params"), dict) else {}
    scene_id = str(params.get("sceneId") or "")
    slot_id = str(params.get("slotId") or "")
    scene_ids = intent.get("sceneIds") if isinstance(intent.get("sceneIds"), list) else []
    if not scene_id and scene_ids:
        scene_id = str(scene_ids[0])
    if scene_id or slot_id:
        index = _find_scene_index(storyboard, scene_id, slot_id)
        if index is not None:
            return storyboard[index]
    return None


def apply_packaging_scene_patch(plan: dict[str, Any], intents: list[dict[str, Any]]) -> dict[str, Any]:
    updated = dict(plan)
    packaging = dict(updated.get("packagingPlan") or {})
    if not packaging:
        packaging = {
            "styleSummary": "Scene packaging patch",
            "subtitle": {},
            "titleCards": [],
            "transitions": [],
        }
    storyboard = [dict(scene) for scene in updated.get("storyboard") or [] if isinstance(scene, dict)]
    overlays = list(packaging.get("sceneOverlays") or [])
    for intent in intents:
        operation = str(intent.get("operation", ""))
        tool = str(intent.get("executionTool") or "")
        if operation != "packaging_scene_patch" and tool != "packaging_scene_patch":
            continue
        scene = _resolve_scene_target(storyboard, intent)
        if scene is None:
            continue
        params = intent.get("params") if isinstance(intent.get("params"), dict) else {}
        scene_id = str(scene.get("id") or "")
        slot_id = str(scene.get("slotId") or "")
        overlay: dict[str, Any] = {
            "sceneId": scene_id,
            "slotId": slot_id,
        }
        for key in ("backgroundPreset", "titleCardPreset", "styleRef", "style"):
            if params.get(key):
                overlay[key if key != "style" else "backgroundPreset"] = str(params[key])
        overlays = [
            item
            for item in overlays
            if not (
                isinstance(item, dict)
                and str(item.get("slotId") or "") == slot_id
            )
        ]
        overlays.append(overlay)
        style = str(params.get("style") or params.get("backgroundPreset") or "")
        if style:
            packaging["styleSummary"] = f"Scene overlay: {style}"
    packaging["sceneOverlays"] = overlays
    updated["packagingPlan"] = packaging
    updated["storyboard"] = storyboard
    return updated


def rebuild_timeline_from_storyboard(
    plan: dict[str, Any],
    generation_root: Path,
) -> dict[str, Any]:
    structure = _read_json(generation_root / "structure-scaled.json") or {}
    inventory = _read_json(generation_root / "asset-inventory.json") or {"assets": []}
    slot_matches_payload = _read_json(generation_root / "slot-matches.json") or {}
    slot_matches = list(slot_matches_payload.get("slotMatches") or [])
    slots_by_id = {slot["id"]: slot for slot in structure.get("slots", []) if isinstance(slot, dict)}
    matches_by_slot = {
        str(m.get("slotId")): m for m in slot_matches if isinstance(m, dict) and m.get("slotId")
    }
    asset_type_by_id = {
        str(a.get("id")): a.get("type")
        for a in inventory.get("assets", [])
        if isinstance(a, dict) and a.get("id")
    }
    storyboard = list(plan.get("storyboard") or [])
    timeline = _build_timeline(
        storyboard=storyboard,
        slot_matches=matches_by_slot,
        slots=slots_by_id,
        asset_type_by_id=asset_type_by_id,
    )
    duration = max((float(s.get("endSec", 0)) for s in storyboard if isinstance(s, dict)), default=0.0)
    timeline["durationSec"] = duration
    packaging = plan.get("packagingPlan") if isinstance(plan.get("packagingPlan"), dict) else {}
    tts_mode = resolve_tts_mode(plan)
    timeline = merge_script_subtitles_into_timeline(
        timeline,
        storyboard,
        packaging,
        skip_subtitles=global_tts_eligible(plan, mode=tts_mode),
    )
    timeline = merge_scene_overlays_into_timeline(timeline, storyboard, packaging)
    updated = dict(plan)
    updated["timeline"] = timeline
    return updated


def _write_patch_audit(
    generation_root: Path,
    *,
    plan: dict[str, Any],
    patch_id: str,
    tools: list[str],
) -> Path:
    audit_root = generation_root / "revise-patches" / patch_id
    audit_root.mkdir(parents=True, exist_ok=True)
    (audit_root / "meta.json").write_text(
        json.dumps(
            {
                "patchId": patch_id,
                "tools": tools,
                "createdAt": _utc_now_iso(),
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (audit_root / "plan-snapshot.json").write_text(
        json.dumps(plan, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return audit_root


def run_revise_patch(
    *,
    project_root: Path,
    project_id: str,
    generation_id: str,
    plan_payload: dict[str, Any],
    emit: EmitFn,
    storage_root: Path,
    use_fixture_render: bool = False,
) -> dict[str, Any]:
    generation_root = generation_artifact_root(project_root, generation_id)
    plan_path = generation_root / "generation-plan.json"
    if not plan_path.is_file():
        return {"ok": False, "error": "generation-plan.json missing"}

    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    _write_snapshot(generation_root, plan)

    intents = list(plan_payload.get("intents") or [])
    steps = list(plan_payload.get("executionSteps") or [])
    tools = [str(s.get("tool", "")) for s in steps if isinstance(s, dict) and s.get("tool")]

    emit(
        status="running",
        stage="applying_revise_patch",
        progress=20,
        message="Applying in-place revise patch",
    )

    if any(t == "subtitle_patch" for t in tools) or any(
        str(i.get("executionTool", "")) == "subtitle_patch" for i in intents
    ):
        plan = apply_subtitle_patch(plan, intents)
    if any(t == "timeline_scene_patch" for t in tools) or any(
        str(i.get("operation", "")) == "timeline_scene_patch" for i in intents
    ):
        plan = apply_timeline_scene_patch(plan, intents)
        plan = rebuild_timeline_from_storyboard(plan, generation_root)
    if any(t == "packaging_scene_patch" for t in tools) or any(
        str(i.get("executionTool", "")) == "packaging_scene_patch" for i in intents
    ):
        plan = apply_packaging_scene_patch(plan, intents)
        plan = rebuild_timeline_from_storyboard(plan, generation_root)

    plan_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")

    patch_id = str(uuid.uuid4())
    _write_patch_audit(generation_root, plan=plan, patch_id=patch_id, tools=tools)

    emit(
        status="running",
        stage="rendering",
        progress=70,
        message="Re-rendering video after patch",
    )

    render_root = generation_root / "renders"
    if render_root.is_dir():
        shutil.rmtree(render_root)
    render_root.mkdir(parents=True, exist_ok=True)

    ffmpeg_tool = build_fixture_ffmpeg_tool() if use_fixture_render else None
    backend = build_render_backend(plan["timeline"], plan=plan, ffmpeg_tool=ffmpeg_tool)

    def render_progress(stage: str) -> None:
        emit(
            status="running",
            stage="rendering",
            progress=85,
            message=f"Rendering ({stage})",
        )

    render_output = backend.render(
        RenderOptions(
            project_id=project_id,
            generation_id=generation_id,
            timeline=plan["timeline"],
            storage_root=storage_root,
            emit_progress=render_progress,
            aspect_ratio=str(plan.get("aspectRatio") or "9:16"),
            tts_mode=str(plan.get("ttsMode") or "") or None,
        )
    )

    if render_output.error and not render_output.artifact_refs:
        emit(
            status="failed",
            stage="rendering",
            progress=90,
            message="Patch render failed",
            error=render_output.error,
        )
        return {"ok": False, "plan": plan, "patchId": patch_id, "error": render_output.error}

    emit(
        status="succeeded",
        stage="completed",
        progress=100,
        message="Revise patch completed",
        artifact_refs=render_output.artifact_refs,
    )
    return {
        "ok": True,
        "plan": plan,
        "patchId": patch_id,
        "renderArtifacts": render_output.artifact_refs,
    }
