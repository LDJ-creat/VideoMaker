from __future__ import annotations

from pathlib import Path

from app.tools.whisper_tool import WhisperTool


class _Segment:
    def __init__(self, start: float, end: float, text: str, no_speech_prob: float = 0.1) -> None:
        self.start = start
        self.end = end
        self.text = text
        self.no_speech_prob = no_speech_prob


def test_missing_fast_whisper_returns_retryable_error(tmp_path: Path) -> None:
    tool = WhisperTool(whisper_model_factory=None)
    result = tool.transcribe(tmp_path / "audio.wav")

    assert result["code"] == "fast_whisper_missing"
    assert result["retryable"] is True


def test_transcribe_normalizes_segments(tmp_path: Path) -> None:
    class _FakeModel:
        def transcribe(self, _: str, language: str = "en"):
            return (
                [
                    _Segment(0.0, 1.2, "hello", no_speech_prob=0.05),
                    _Segment(1.2, 2.6, "world", no_speech_prob=0.15),
                ],
                {"language": language},
            )

    tool = WhisperTool(whisper_model_factory=lambda: _FakeModel())
    result = tool.transcribe(tmp_path / "audio.wav")

    assert result["segments"][0] == {
        "startSec": 0.0,
        "endSec": 1.2,
        "text": "hello",
        "confidence": 0.95,
    }
    assert len(result["segments"]) == 2
