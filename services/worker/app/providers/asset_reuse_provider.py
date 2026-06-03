from __future__ import annotations

from pathlib import Path
from typing import Any

from app.providers.material_types import MaterialContext, MaterialResult
from app.tools.ffmpeg_tool import FFmpegTool


class AssetReuseProvider:
    name = "asset_reuse"

    def __init__(self, ffmpeg_tool: FFmpegTool | None = None) -> None:
        self._ffmpeg = ffmpeg_tool or FFmpegTool()

    def execute(self, action: dict[str, Any], ctx: MaterialContext) -> MaterialResult:
        slot_id = str(action["slotId"])
        ctx.emit_progress("rendering_material", f"Trimming reused asset for {slot_id}")
        match = _match_for_slot(slot_id, ctx.slot_matches)
        if match is None:
            return _error(action, slot_id, "asset_reuse_no_match", "No weak match available for reuse")

        moment = _moment_for_match(match, ctx.inventory)
        asset = _asset_by_id(str(match.get("assetId", "")), ctx.inventory)
        if asset is None:
            return _error(action, slot_id, "asset_reuse_missing_asset", "Matched asset not found in inventory")

        if str(asset.get("type", "")).lower() == "image":
            return _error(
                action,
                slot_id,
                "asset_reuse_image_not_supported",
                "Image assets must use video_generation (i2v), not asset_reuse",
            )

        scene = _scene_for_slot(slot_id, ctx.storyboard)
        duration = max(0.1, float(scene["endSec"]) - float(scene["startSec"])) if scene else 3.0
        output_path = ctx.generated_root / f"{slot_id}-reuse.mp4"

        source_path = _resolve_asset_path(asset, moment)
        if source_path is None:
            return _error(action, slot_id, "asset_reuse_missing_source", "Asset source path is unavailable")

        trim_result = self._ffmpeg.trim_clip(
            source_path,
            output_path,
            start_sec=float(moment.get("startSec", 0.0)) if moment else 0.0,
            duration_sec=duration,
        )
        if trim_result.get("code"):
            return {
                "ok": False,
                "actionId": action["id"],
                "slotId": slot_id,
                "provider": self.name,
                "error": {
                    "code": str(trim_result.get("code", "asset_reuse_trim_failed")),
                    "message": str(trim_result.get("message", "ffmpeg trim failed")),
                    "retryable": bool(trim_result.get("retryable", True)),
                },
            }

        registered = ctx.register_artifact("video", output_path)
        return {
            "ok": True,
            "actionId": action["id"],
            "slotId": slot_id,
            "provider": self.name,
            "artifactRef": registered,
        }


def _error(action: dict[str, Any], slot_id: str, code: str, message: str) -> MaterialResult:
    return {
        "ok": False,
        "actionId": action["id"],
        "slotId": slot_id,
        "provider": "asset_reuse",
        "error": {"code": code, "message": message, "retryable": False},
    }


def _match_for_slot(slot_id: str, slot_matches: list[dict[str, Any]]) -> dict[str, Any] | None:
    for match in slot_matches:
        if match.get("slotId") == slot_id:
            return match
    return None


def _moment_for_match(match: dict[str, Any], inventory: dict[str, Any]) -> dict[str, Any] | None:
    moment_id = match.get("momentId")
    if not moment_id:
        return None
    for moment in inventory.get("candidateMoments", []):
        if moment.get("id") == moment_id:
            return moment
    return None


def _asset_by_id(asset_id: str, inventory: dict[str, Any]) -> dict[str, Any] | None:
    for asset in inventory.get("assets", []):
        if asset.get("id") == asset_id:
            return asset
    return None


def _scene_for_slot(slot_id: str, storyboard: list[dict[str, Any]]) -> dict[str, Any] | None:
    for scene in storyboard:
        if scene.get("slotId") == slot_id:
            return scene
    return None


def _resolve_asset_path(asset: dict[str, Any], moment: dict[str, Any] | None) -> Path | None:
    _ = moment
    uri = str(asset.get("uri", "")).strip()
    if not uri:
        return None
    path = Path(uri)
    if path.is_file():
        return path
    if uri.startswith("file://"):
        candidate = Path(uri.removeprefix("file://"))
        if candidate.is_file():
            return candidate
    return None
