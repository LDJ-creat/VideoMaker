from __future__ import annotations

import io
import struct
import wave
from pathlib import Path
from unittest.mock import MagicMock

from app.pipelines.tts_mode import MASTER_TTS_SLOT_ID
from app.providers.completion_registry import MaterialContext, register_default_providers
from app.providers.tts_provider import TTSProvider
from app.runtime.video_gen_quota import VideoGenQuota
from app.tools.tts_tool import TTSTool


def _wav_bytes() -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(24000)
        handle.writeframes(struct.pack("<h", 0) * 2400)
    return buffer.getvalue()


def _make_ctx(tmp_path: Path, *, gateway: MagicMock) -> MaterialContext:
    generated_root = tmp_path / "generated"
    generated_root.mkdir(parents=True, exist_ok=True)
    return MaterialContext(
        project_id="project-1",
        generation_id="gen-1",
        render_root=tmp_path / "renders" / "gen-1",
        generated_root=generated_root,
        gateway=gateway,
        quota=VideoGenQuota(),
        inventory={"assets": []},
        slot_matches=[],
        storyboard=[
            {
                "slotId": "slot-hook",
                "script": "你好，这是口播",
                "voDirective": {"pace": "fast"},
            }
        ],
        structure={},
        emit_progress=lambda *_args, **_kwargs: None,
        register_artifact=lambda artifact_type, path: {
            "type": artifact_type,
            "uri": str(Path(path).resolve()),
        },
        master_narration="你好，这是口播",
        narration_vo_profile={"energy": "high"},
    )


def test_tts_provider_emits_directive_ignored_for_openai_compatible(tmp_path: Path) -> None:
    gateway = MagicMock()
    gateway.config = MagicMock()
    gateway.config.tts_preferences = {}
    gateway.config.tts_driver = "openai_compatible"
    gateway.synthesize_speech.return_value = _wav_bytes()

    progress: list[tuple[str, str]] = []
    ctx = _make_ctx(tmp_path, gateway=gateway)
    ctx.emit_progress = lambda stage, message: progress.append((stage, message))

    provider = TTSProvider(TTSTool(gateway=gateway))
    result = provider.execute(
        {
            "id": "action-master-tts",
            "slotId": MASTER_TTS_SLOT_ID,
            "provider": "tts",
        },
        ctx,
    )

    assert result["ok"] is True
    assert ("tts_directive_ignored", "VO directives ignored for non-volcengine TTS") in progress
    assert ctx.tts_directive_warning_emitted is True


def test_tts_provider_skips_directive_warning_for_volcengine(tmp_path: Path) -> None:
    gateway = MagicMock()
    gateway.config = MagicMock()
    gateway.config.tts_preferences = {}
    gateway.config.tts_driver = "volcengine_tts"
    gateway.synthesize_speech.return_value = _wav_bytes()

    progress: list[tuple[str, str]] = []
    ctx = _make_ctx(tmp_path, gateway=gateway)
    ctx.emit_progress = lambda stage, message: progress.append((stage, message))

    provider = TTSProvider(TTSTool(gateway=gateway))
    result = provider.execute(
        {
            "id": "action-master-tts",
            "slotId": MASTER_TTS_SLOT_ID,
            "provider": "tts",
        },
        ctx,
    )

    assert result["ok"] is True
    assert not any(stage == "tts_directive_ignored" for stage, _ in progress)


def test_tts_provider_rejects_non_master_slot(tmp_path: Path) -> None:
    gateway = MagicMock()
    gateway.config = MagicMock()
    gateway.config.tts_preferences = {}
    ctx = _make_ctx(tmp_path, gateway=gateway)
    provider = TTSProvider(TTSTool(gateway=gateway))
    result = provider.execute(
        {"id": "action-hook", "slotId": "slot-hook", "provider": "tts"},
        ctx,
    )
    assert result["ok"] is False
    assert result["error"]["code"] == "unsupported_tts_slot"
