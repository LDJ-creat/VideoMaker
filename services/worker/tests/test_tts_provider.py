from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from app.pipelines.tts_mode import MASTER_TTS_SLOT_ID
from app.providers.material_types import MaterialContext
from app.providers.tts_provider import TTSProvider
from app.runtime.video_gen_quota import VideoGenQuota
from app.tools.tts_tool import TTSTool
from tests.helpers.canonical_narration_fixture import write_canonical_fixture


def _make_ctx(tmp_path: Path, *, gateway: MagicMock) -> MaterialContext:
    render_root = tmp_path / "renders" / "gen-1"
    render_root.mkdir(parents=True, exist_ok=True)
    generated_root = tmp_path / "generations" / "gen-1" / "generated"
    generated_root.mkdir(parents=True, exist_ok=True)
    return MaterialContext(
        project_id="project-1",
        generation_id="gen-1",
        render_root=render_root,
        generated_root=generated_root,
        gateway=gateway,
        quota=VideoGenQuota(),
        inventory={"assets": []},
        slot_matches=[],
        storyboard=[
            {
                "slotId": "slot-hook",
                "startSec": 0.0,
                "endSec": 1.0,
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


def test_tts_provider_reuses_canonical_master_wav(tmp_path: Path) -> None:
    gateway = MagicMock()
    gateway.config = MagicMock()
    gateway.config.tts_preferences = {}
    gateway.config.tts_driver = "openai_compatible"

    progress: list[tuple[str, str]] = []
    ctx = _make_ctx(tmp_path, gateway=gateway)
    ctx.emit_progress = lambda stage, message: progress.append((stage, message))
    write_canonical_fixture(ctx)

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
    assert ("canonical_tts_reused", "Reused canonical narration master.wav") in progress
    assert (ctx.generated_root / "master.wav").is_file()


def test_tts_provider_fails_when_canonical_missing(tmp_path: Path) -> None:
    gateway = MagicMock()
    gateway.config = MagicMock()
    gateway.config.tts_preferences = {}
    ctx = _make_ctx(tmp_path, gateway=gateway)
    provider = TTSProvider(TTSTool(gateway=gateway))
    result = provider.execute(
        {
            "id": "action-master-tts",
            "slotId": MASTER_TTS_SLOT_ID,
            "provider": "tts",
        },
        ctx,
    )
    assert result["ok"] is False
    assert result["error"]["code"] == "canonical_narration_unavailable"


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
