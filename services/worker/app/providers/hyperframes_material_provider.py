from __future__ import annotations

from pathlib import Path
from typing import Any

from app.agents.material_author import run_material_author_with_runner
from app.providers.material_types import MaterialContext, MaterialResult
from app.tools.hyperframes_material_tool import HyperFramesMaterialTool
from app.validation.material_spec_coercer import build_ken_burns_spec


def _slot_by_id(structure: dict[str, Any], slot_id: str) -> dict[str, Any]:
    for slot in structure.get("slots", []):
        if isinstance(slot, dict) and slot.get("id") == slot_id:
            return slot
    raise ValueError(f"Structure slot not found: {slot_id}")


def _material_author_slot(slot: dict[str, Any]) -> dict[str, Any]:
    return {
        "role": slot.get("role"),
        "scriptIntent": slot.get("scriptIntent", ""),
        "visualIntent": slot.get("visualIntent", ""),
        "importance": slot.get("importance"),
        "requiredAssetType": list(slot.get("requiredAssetType") or []),
    }


def _stock_image_refs(generated_root: Path, slot_id: str) -> list[dict[str, Any]] | None:
    for suffix in (".jpg", ".png", ".webp"):
        candidate = generated_root / f"{slot_id}-stock{suffix}"
        if candidate.is_file() and candidate.stat().st_size > 0:
            return [
                {
                    "id": f"stock-{slot_id}",
                    "type": "image",
                    "uri": str(candidate.resolve()),
                    "createdAt": "1970-01-01T00:00:00Z",
                }
            ]
    return None


def _duration_for_slot(ctx: MaterialContext, slot_id: str) -> float:
    for scene in ctx.storyboard:
        if isinstance(scene, dict) and scene.get("slotId") == slot_id:
            return max(0.5, float(scene["endSec"]) - float(scene["startSec"]))
    return 4.0


def _resolve_material_asset_refs(
    action: dict[str, Any],
    ctx: MaterialContext,
    *,
    slot_id: str,
) -> list[dict[str, Any]] | None:
    refs = action.get("assetRefs")
    if isinstance(refs, list) and refs:
        return refs
    return _stock_image_refs(ctx.generated_root, slot_id)


def expected_hyperframes_output(action: dict[str, Any], generated_root: Path) -> Path:
    slot_id = str(action["slotId"])
    action_id = str(action.get("id") or f"action-{slot_id}")
    return generated_root / f"{action_id}.mp4"


class HyperFramesMaterialProvider:
    name = "hyperframes_material"

    def __init__(self, tool: HyperFramesMaterialTool | None = None) -> None:
        self._tool = tool

    def execute(self, action: dict[str, Any], ctx: MaterialContext) -> MaterialResult:
        slot_id = str(action["slotId"])
        action_id = str(action.get("id") or f"action-{slot_id}")
        try:
            slot = _slot_by_id(ctx.structure, slot_id)
        except ValueError as exc:
            return _failure(action, slot_id, code="slot_not_found", message=str(exc))

        asset_refs = _resolve_material_asset_refs(action, ctx, slot_id=slot_id)
        spec = action.get("materialSpec")
        if spec is None and str(action_id).endswith("-ken-burns"):
            stock_video = ctx.generated_root / f"{slot_id}-stock.mp4"
            if stock_video.is_file() and stock_video.stat().st_size > 0:
                return _failure(
                    action,
                    slot_id,
                    code="ken_burns_not_needed",
                    message="Stock video already materialized for slot; skip ken-burns chain step",
                    retryable=False,
                )
            if asset_refs:
                spec = build_ken_burns_spec(
                    asset_refs,
                    duration_sec=_duration_for_slot(ctx, slot_id),
                )
        if spec is None:
            if ctx.runner is None or ctx.task_context is None:
                return _failure(
                    action,
                    slot_id,
                    code="material_author_unavailable",
                    message="materialSpec missing and AgentRunner/TaskContext not configured",
                    retryable=False,
                )
            spec = run_material_author_with_runner(
                ctx.runner,
                slot=_material_author_slot(slot),
                context=ctx.task_context,
                variant_overrides=ctx.variant_overrides,
                brand_colors=ctx.brand_colors,
                asset_refs=asset_refs,
                generation_id=ctx.generation_id,
            )

        output_dir = ctx.generated_root / action_id / "composition"
        output_clip = expected_hyperframes_output(action, ctx.generated_root)
        log_path = ctx.generated_root / f"{action_id}-render-log.json"
        ctx.generated_root.mkdir(parents=True, exist_ok=True)

        tool = self._tool or HyperFramesMaterialTool()
        render_result = tool.render_material(
            spec,
            project_root=ctx.project_root,
            output_dir=output_dir,
            output_clip=output_clip,
            log_path=log_path,
            asset_root=ctx.generated_root,
            aspect_ratio=ctx.aspect_ratio,
        )
        if not render_result.get("ok"):
            error = render_result.get("error") or {}
            return {
                "ok": False,
                "actionId": action_id,
                "slotId": slot_id,
                "provider": self.name,
                "error": {
                    "code": str(error.get("code", "material_render_failed")),
                    "message": str(error.get("message", "HyperFrames material render failed")),
                    "retryable": bool(error.get("retryable", False)),
                },
            }

        registered = ctx.register_artifact("video", output_clip)
        ctx.emit_progress(
            "rendering_material",
            f"HyperFrames material ready for slot {slot_id}",
        )
        return {
            "ok": True,
            "actionId": action_id,
            "slotId": slot_id,
            "provider": self.name,
            "artifactRef": registered,
            "clipDurationSec": float(render_result.get("durationSec", spec.get("durationSec", 0))),
        }


def _failure(
    action: dict[str, Any],
    slot_id: str,
    *,
    code: str,
    message: str,
    retryable: bool = False,
) -> MaterialResult:
    return {
        "ok": False,
        "actionId": str(action.get("id", "")),
        "slotId": slot_id,
        "provider": "hyperframes_material",
        "error": {
            "code": code,
            "message": message,
            "retryable": retryable,
        },
    }
