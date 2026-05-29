from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.tools.image_gen_tool import ToolError
from app.tools.tts_tool import TTSTool


def test_synthesize_writes_audio_and_emits_stage(tmp_path: Path) -> None:
    wav = b"RIFF----WAVEfmt "
    gateway = MagicMock()
    gateway.synthesize_speech.return_value = wav
    emitted: list[tuple[str, str]] = []

    tool = TTSTool(
        gateway=gateway,
        emit_progress=lambda stage, message: emitted.append((stage, message)),
    )
    output_path = tmp_path / "voice.wav"
    ref = tool.synthesize(text="hello world", output_path=output_path, voice="alloy")

    assert output_path.read_bytes() == wav
    gateway.synthesize_speech.assert_called_once_with("hello world", options={"voice": "alloy"})
    assert ref["type"] == "audio"
    assert emitted == [("generating_tts", "Synthesizing speech")]


def test_synthesize_wraps_gateway_errors(tmp_path: Path) -> None:
    gateway = MagicMock()
    gateway.synthesize_speech.side_effect = RuntimeError("tts down")
    tool = TTSTool(gateway=gateway)

    with pytest.raises(ToolError) as exc_info:
        tool.synthesize(text="x", output_path=tmp_path / "out.wav")

    assert exc_info.value.code == "tts_failed"
    assert exc_info.value.retryable is True
