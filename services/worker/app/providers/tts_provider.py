from __future__ import annotations

from typing import Any

from app.pipelines.narration_scene_timing import reconcile_storyboard_to_segment_durations
from app.pipelines.tts_mode import MASTER_TTS_SLOT_ID, MASTER_TTS_WAV_NAME
from app.pipelines.tts_synthesis import synthesize_master_wav
from app.providers.material_types import MaterialContext, MaterialResult
from app.providers.tts_preview_reuse import try_reuse_preview_master_wav
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
            if try_reuse_preview_master_wav(ctx, output_path):
                registered = ctx.register_artifact("audio", output_path)
                return {
                    "ok": True,
                    "actionId": action["id"],
                    "slotId": slot_id,
                    "provider": self.name,
                    "artifactRef": registered,
                }
            has_vo_directives = bool(ctx.narration_vo_profile) or any(
                isinstance(scene.get("voDirective"), dict)
                for scene in ctx.storyboard
                if isinstance(scene, dict)
            )
            tts_driver = str(getattr(getattr(ctx.gateway, "config", None), "tts_driver", "") or "")
            if has_vo_directives and tts_driver and tts_driver != "volcengine_tts":
                if not ctx.tts_directive_warning_emitted:
                    ctx.emit_progress(
                        "tts_directive_ignored",
                        "VO directives ignored for non-volcengine TTS",
                    )
                    ctx.tts_directive_warning_emitted = True
            artifact_ref = synthesize_master_wav(
                tool=self._tool,
                master_narration=text,
                storyboard=list(ctx.storyboard),
                structure=ctx.structure,
                workbench_prefs=ctx.gateway.config.tts_preferences,
                generation_id=ctx.generation_id,
                narration_vo_profile=ctx.narration_vo_profile,
                output_path=output_path,
            )
            segment_durations = artifact_ref.get("segmentDurations")
            if isinstance(segment_durations, list) and segment_durations:
                ctx.storyboard = reconcile_storyboard_to_segment_durations(
                    list(ctx.storyboard),
                    segment_durations=[
                        (str(slot_id), float(duration))
                        for slot_id, duration in segment_durations
                        if slot_id and duration > 0
                    ],
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
        registered = ctx.register_artifact(artifact_ref["type"], artifact_ref["uri"])
        return {
            "ok": True,
            "actionId": action["id"],
            "slotId": slot_id,
            "provider": self.name,
            "artifactRef": registered,
        }
