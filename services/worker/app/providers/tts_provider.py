from __future__ import annotations

from typing import Any

from app.pipelines.tts_mode import MASTER_TTS_SLOT_ID, MASTER_TTS_WAV_NAME
from app.pipelines.tts_voice_options import build_tts_synthesis_options
from app.providers.material_types import MaterialContext, MaterialResult
from app.tools.image_gen_tool import ToolError
from app.tools.tts_tool import TTSTool


class TTSProvider:
    name = "tts"

    def __init__(self, tool: TTSTool) -> None:
        self._tool = tool

    def execute(self, action: dict[str, Any], ctx: MaterialContext) -> MaterialResult:
        slot_id = str(action["slotId"])
        if slot_id == MASTER_TTS_SLOT_ID:
            text = str(ctx.master_narration).strip()
            if not text:
                return {
                    "ok": False,
                    "actionId": action["id"],
                    "slotId": slot_id,
                    "provider": self.name,
                    "error": {
                        "code": "missing_master_narration",
                        "message": "masterNarration is required for global TTS",
                        "retryable": False,
                    },
                }
            output_path = ctx.generated_root / MASTER_TTS_WAV_NAME
        else:
            text = _script_for_slot(ctx, slot_id)
            output_path = ctx.generated_root / f"{slot_id}.wav"
        options = build_tts_synthesis_options(
            structure=ctx.structure,
            workbench_prefs=ctx.gateway.config.tts_preferences,
            generation_id=ctx.generation_id,
        )
        try:
            artifact_ref = self._tool.synthesize(
                text=text,
                output_path=output_path,
                options=options,
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


def _script_for_slot(ctx: MaterialContext, slot_id: str) -> str:
    for scene in ctx.storyboard:
        if scene.get("slotId") == slot_id:
            script = str(scene.get("script", "")).strip()
            if script:
                return script
    return f"Narration for slot {slot_id}"
