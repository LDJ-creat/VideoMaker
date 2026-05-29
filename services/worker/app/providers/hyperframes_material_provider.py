from __future__ import annotations

from pathlib import Path
from typing import Any

from app.agents.material_author import run_material_author_with_runner
from app.providers.material_types import MaterialContext, MaterialResult
from app.tools.hyperframes_material_tool import HyperFramesMaterialTool


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

        spec = action.get("materialSpec")
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
                asset_refs=action.get("assetRefs"),
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
