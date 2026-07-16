from __future__ import annotations

from typing import Any

from app.pipelines.tts_mode import MASTER_TTS_SLOT_ID, MASTER_TTS_WAV_NAME
from app.providers.canonical_tts_reuse import try_reuse_canonical_master_wav
from app.providers.material_types import MaterialContext, MaterialResult
from app.tools.image_gen_tool import ToolError
from app.tools.tts_tool import TTSTool


class TTSProvider:
    name = "tts"

    def __init__(self, tool: TTSTool) -> None:
        self._tool = tool

    def execute(self, action: dict[str, Any], ctx: MaterialContext) -> MaterialResult:
        slot_id = str(action["slotId"])
        if slot_id != MASTER_TTS_SLOT_ID:
            return {
                "ok": False,
                "actionId": action["id"],
                "slotId": slot_id,
                "provider": self.name,
                "error": {
                    "code": "unsupported_tts_slot",
                    "message": "Only global master TTS is supported",
                    "retryable": False,
                },
            }

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
        try:
            if try_reuse_canonical_master_wav(ctx, output_path):
                registered = ctx.register_artifact("audio", output_path)
                return {
                    "ok": True,
                    "actionId": action["id"],
                    "slotId": slot_id,
                    "provider": self.name,
                    "artifactRef": registered,
                }
            return {
                "ok": False,
                "actionId": action["id"],
                "slotId": slot_id,
                "provider": self.name,
                "error": {
                    "code": "canonical_narration_unavailable",
                    "message": (
                        "Canonical narration audio is missing or stale; "
                        "re-run synthesizing_canonical_narration before assembly"
                    ),
                    "retryable": True,
                },
            }
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
        except ValueError as exc:
            return {
                "ok": False,
                "actionId": action["id"],
                "slotId": slot_id,
                "provider": self.name,
                "error": {
                    "code": "tts_failed",
                    "message": str(exc),
                    "retryable": False,
                },
            }
