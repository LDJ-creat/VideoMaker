from __future__ import annotations

from pathlib import Path
from typing import Any

from app.pipelines.visual_style_bible import augment_slot_generation_prompt
from app.providers.material_types import MaterialContext, MaterialResult
from app.tools.image_gen_tool import ImageGenTool, ToolError


class ImageGenerationProvider:
    name = "image_generation"

    def __init__(self, tool: ImageGenTool) -> None:
        self._tool = tool

    def execute(self, action: dict[str, Any], ctx: MaterialContext) -> MaterialResult:
        slot_id = str(action["slotId"])
        prompt = _prompt_for_slot(ctx, slot_id)
        output_path = ctx.generated_root / f"{slot_id}.png"
        try:
            artifact_ref = self._tool.generate(prompt=prompt, output_path=output_path)
        except ToolError as exc:
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


def _prompt_for_slot(ctx: MaterialContext, slot_id: str) -> str:
    for scene in ctx.storyboard:
        if scene.get("slotId") == slot_id:
            visual = str(scene.get("visual", "")).strip()
            script = str(scene.get("script", "")).strip()
            if visual and script:
                base = f"{visual}. Narration context: {script}"
            else:
                base = visual or script or f"Generate visual for slot {slot_id}"
            return augment_slot_generation_prompt(base, ctx.visual_style_bible)
    return augment_slot_generation_prompt(
        f"Generate visual for slot {slot_id}",
        ctx.visual_style_bible,
    )
