from __future__ import annotations

from typing import Any

from app.providers.material_types import MaterialContext, MaterialResult
from app.tools.image_gen_tool import ToolError
from app.tools.tts_tool import TTSTool


class TTSProvider:
    name = "tts"

    def __init__(self, tool: TTSTool) -> None:
        self._tool = tool

    def execute(self, action: dict[str, Any], ctx: MaterialContext) -> MaterialResult:
        slot_id = str(action["slotId"])
        text = _script_for_slot(ctx, slot_id)
        output_path = ctx.generated_root / f"{slot_id}.wav"
        try:
            artifact_ref = self._tool.synthesize(text=text, output_path=output_path)
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


def _script_for_slot(ctx: MaterialContext, slot_id: str) -> str:
    for scene in ctx.storyboard:
        if scene.get("slotId") == slot_id:
            script = str(scene.get("script", "")).strip()
            if script:
                return script
    return f"Narration for slot {slot_id}"
