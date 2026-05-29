from __future__ import annotations

from typing import Any

from app.providers.material_types import MaterialContext, MaterialResult
from app.providers.image_generation_provider import _prompt_for_slot
from app.tools.image_gen_tool import ToolError
from app.tools.video_gen_tool import VideoGenTool


class VideoGenerationProvider:
    name = "video_generation"

    def __init__(self, tool: VideoGenTool) -> None:
        self._tool = tool

    def execute(self, action: dict[str, Any], ctx: MaterialContext) -> MaterialResult:
        slot_id = str(action["slotId"])
        prompt = _prompt_for_slot(ctx, slot_id)
        output_path = ctx.generated_root / f"{slot_id}.mp4"
        try:
            artifact_ref = self._tool.generate(
                prompt=prompt,
                output_path=output_path,
                quota=ctx.quota,
            )
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
