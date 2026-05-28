from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable

WhisperModelFactory = Callable[[], Any]

WHISPER_SOFT_FAIL_CODES = frozenset(
    {
        "fast_whisper_missing",
        "fast_whisper_model_unavailable",
        "fast_whisper_failed",
        "fast_whisper_skipped",
    }
)


def _retryable_error(code: str, message: str) -> dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "retryable": True,
    }


def _env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def configure_whisper_runtime() -> None:
    """Best-effort Hugging Face download settings for first model fetch."""
    os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "600")
    os.environ.setdefault("HF_HUB_ETAG_TIMEOUT", "60")


class WhisperTool:
    def __init__(self, whisper_model_factory: WhisperModelFactory | None = "auto") -> None:
        self._whisper_model_factory = whisper_model_factory

    def _build_model(self) -> Any:
        if self._whisper_model_factory is None:
            raise ImportError("fast-whisper unavailable")
        if self._whisper_model_factory != "auto":
            return self._whisper_model_factory()

        configure_whisper_runtime()
        from faster_whisper import WhisperModel  # type: ignore

        model_dir = os.environ.get("VIDEOMAKER_WHISPER_MODEL_DIR", "").strip()
        if model_dir and Path(model_dir).is_dir():
            return WhisperModel(model_dir, compute_type="int8")

        model_name = os.environ.get("VIDEOMAKER_WHISPER_MODEL", "tiny").strip() or "tiny"
        return WhisperModel(model_name, compute_type="int8")

    def transcribe(self, audio_path: str | Path) -> dict[str, Any]:
        if _env_truthy("VIDEOMAKER_SKIP_WHISPER"):
            return _retryable_error(
                "fast_whisper_skipped",
                "Whisper transcription disabled by VIDEOMAKER_SKIP_WHISPER",
            )

        try:
            model = self._build_model()
        except ImportError:
            return _retryable_error("fast_whisper_missing", "fast-whisper is not installed")
        except Exception as exc:
            return _retryable_error(
                "fast_whisper_model_unavailable",
                "Whisper model download or load failed. "
                "Use HF mirror / HF_TOKEN, set VIDEOMAKER_WHISPER_MODEL_DIR, "
                "or set VIDEOMAKER_SKIP_WHISPER=1. "
                f"Details: {exc}",
            )

        try:
            segments, info = model.transcribe(
                str(Path(audio_path).resolve()),
                language=None,
                vad_filter=True,
            )
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
