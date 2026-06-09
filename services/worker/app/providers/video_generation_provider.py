from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from app.pipelines.visual_style_bible import augment_slot_generation_prompt
from app.runtime.asset_paths import asset_by_id, resolve_asset_path, resolve_match_asset_type
from app.providers.material_types import MaterialContext, MaterialResult
from app.tools.image_gen_tool import ToolError
from app.tools.video_gen_tool import VideoGenTool


class VideoGenerationProvider:
    name = "video_generation"

    def __init__(self, tool: VideoGenTool) -> None:
        self._tool = tool

    def execute(self, action: dict[str, Any], ctx: MaterialContext) -> MaterialResult:
        slot_id = str(action["slotId"])
        ctx.emit_progress("generating_video", f"Generating video for {slot_id}")

        prompt = _prompt_for_slot(ctx, slot_id)
        duration_sec = _duration_for_slot(ctx, slot_id)
        weak_match = _match_for_slot(slot_id, ctx.slot_matches)
        asset_type = resolve_match_asset_type(weak_match, ctx.inventory)
        mode = "i2v" if asset_type == "image" and weak_match else "t2v"
        reference_path: Path | None = None
        if mode == "i2v" and weak_match:
            asset = asset_by_id(str(weak_match.get("assetId", "")), ctx.inventory)
            if asset is not None:
                reference_path = resolve_asset_path(asset)
            if reference_path is None:
                mode = "t2v"

        options: dict[str, Any] = {
            "mode": mode,
            "durationSec": duration_sec,
            "slotId": slot_id,
            "resolution": os.getenv("VIDEO_DEFAULT_RESOLUTION", "720P"),
        }
        if mode == "i2v" and reference_path is not None:
            options["referenceImagePath"] = str(reference_path)

        output_path = ctx.generated_root / f"{slot_id}.mp4"
        try:
            artifact_ref = self._tool.generate(
                prompt=prompt,
                output_path=output_path,
                quota=ctx.quota,
                options=options,
            )
        except ToolError as exc:
            fallback = os.getenv("VIDEOMAKER_VIDEO_GEN_FALLBACK", "").strip().lower()
            if fallback in {"image_generation", "hyperframes_material"}:
                return {
                    "ok": False,
                    "actionId": action["id"],
                    "slotId": slot_id,
                    "provider": self.name,
                    "error": {
                        "code": exc.code,
                        "message": exc.message,
                        "retryable": exc.retryable,
                        "fallbackProvider": fallback,
                    },
                }
            return {
                "ok": False,
                "actionId": action["id"],
                "slotId": slot_id,
                "provider": self.name,
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "retryable": exc.retryable,
                },
            }

        registered = ctx.register_artifact(artifact_ref["type"], artifact_ref["uri"])
        return {
            "ok": True,
            "actionId": action["id"],
            "slotId": slot_id,
            "provider": self.name,
            "artifactRef": registered,
        }


def _match_for_slot(slot_id: str, slot_matches: list[dict[str, Any]]) -> dict[str, Any] | None:
    for match in slot_matches:
        if match.get("slotId") == slot_id:
            return match
    return None


def _duration_for_slot(ctx: MaterialContext, slot_id: str) -> float:
    for scene in ctx.storyboard:
        if scene.get("slotId") == slot_id:
            return max(0.1, float(scene["endSec"]) - float(scene["startSec"]))
    for slot in ctx.structure.get("slots", []):
        if isinstance(slot, dict) and slot.get("id") == slot_id:
            return max(
                0.1,
                float(slot.get("endSec", 0)) - float(slot.get("startSec", 0)),
            )
    return 5.0


def _prompt_for_slot(ctx: MaterialContext, slot_id: str) -> str:
    structure_slot = None
    for slot in ctx.structure.get("slots", []):
        if isinstance(slot, dict) and slot.get("id") == slot_id:
            structure_slot = slot
            break

    visual = ""
    script = ""
    for scene in ctx.storyboard:
        if scene.get("slotId") == slot_id:
            visual = str(scene.get("visual", "")).strip()
            script = str(scene.get("script", "")).strip()
            break

    if structure_slot:
        visual_intent = str(structure_slot.get("visualIntent", "")).strip()
        script_intent = str(structure_slot.get("scriptIntent", "")).strip()
        if visual_intent:
            visual = visual or visual_intent
        if script_intent:
            script = script or script_intent

    weak_match = _match_for_slot(slot_id, ctx.slot_matches)
    if resolve_match_asset_type(weak_match, ctx.inventory) == "image":
        prefix = (
            "Animate this product/scene image as a short video clip. "
            "Keep the main subject and branding consistent with the reference frame. "
        )
        body = f"{visual}. {script}".strip() if visual or script else f"Slot {slot_id} video"
        return augment_slot_generation_prompt(prefix + body, ctx.visual_style_bible)

    if visual and script:
        base = f"{visual}. Narration context: {script}"
    else:
        base = visual or script or f"Generate short-form video clip for slot {slot_id}"
    return augment_slot_generation_prompt(base, ctx.visual_style_bible)
