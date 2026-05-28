from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

WhisperModelFactory = Callable[[], Any]


def _retryable_error(code: str, message: str) -> dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "retryable": True,
    }


class WhisperTool:
    def __init__(self, whisper_model_factory: WhisperModelFactory | None = "auto") -> None:
        self._whisper_model_factory = whisper_model_factory

    def _build_model(self) -> Any:
        if self._whisper_model_factory is None:
            raise ImportError("fast-whisper unavailable")
        if self._whisper_model_factory != "auto":
            return self._whisper_model_factory()

        from faster_whisper import WhisperModel  # type: ignore

        return WhisperModel("small", compute_type="int8")

    def transcribe(self, audio_path: str | Path) -> dict[str, Any]:
        try:
            model = self._build_model()
        except ImportError:
            return _retryable_error("fast_whisper_missing", "fast-whisper is not installed")

        try:
            segments, info = model.transcribe(str(Path(audio_path).resolve()), language="en")
        except Exception as exc:  # pragma: no cover - guarded runtime fallback
            return _retryable_error("fast_whisper_failed", f"transcription failed: {exc}")

        normalized_segments: list[dict[str, Any]] = []
        for segment in segments:
            no_speech_prob = float(getattr(segment, "no_speech_prob", 0.0))
            confidence = max(0.0, min(1.0, 1.0 - no_speech_prob))
            normalized_segments.append(
                {
                    "startSec": round(float(segment.start), 3),
                    "endSec": round(float(segment.end), 3),
                    "text": str(segment.text).strip(),
                    "confidence": round(confidence, 3),
                }
            )

        return {
            "language": getattr(info, "language", "unknown")
            if not isinstance(info, dict)
            else info.get("language", "unknown"),
            "segments": normalized_segments,
        }
