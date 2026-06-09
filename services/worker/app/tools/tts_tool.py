from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from app.gateway.model_gateway import ModelGateway
from app.tools.image_gen_tool import ToolError, _artifact_ref

ProgressEmitter = Callable[[str, str], None]


class TTSTool:
    def __init__(
        self,
        *,
        gateway: ModelGateway,
        emit_progress: ProgressEmitter | None = None,
    ) -> None:
        self._gateway = gateway
        self._emit_progress = emit_progress

    def synthesize(
        self,
        *,
        text: str,
        output_path: Path,
        voice: str = "default",
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if self._emit_progress is not None:
            self._emit_progress("generating_tts", "Synthesizing speech")
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        merged: dict[str, Any] = dict(options or {})
        if voice != "default" and "speaker" not in merged and "voice" not in merged:
            merged["voice"] = voice
        try:
            audio_bytes = self._gateway.synthesize_speech(
                text,
                options=merged or None,
            )
        except Exception as exc:
            raise ToolError(
                code="tts_failed",
                message=str(exc),
                retryable=True,
            ) from exc
        output_path.write_bytes(audio_bytes)
        return _artifact_ref("audio", output_path)
