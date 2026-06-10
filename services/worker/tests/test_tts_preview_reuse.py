from __future__ import annotations

import shutil
import struct
import wave
from pathlib import Path
from unittest.mock import MagicMock

from app.pipelines.narration_scene_timing import narration_content_hash, save_narration_preview
from app.providers.material_types import MaterialContext
from app.providers.tts_preview_reuse import try_reuse_preview_master_wav


def _write_wav(path: Path, *, seconds: float = 2.0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = int(24000 * seconds)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(24000)
        handle.writeframes(struct.pack("<h", 0) * frames)


def _ctx(tmp_path: Path, generation_id: str = "gen-1") -> MaterialContext:
    project_root = tmp_path / "projects" / "proj-1"
    render_root = project_root / "renders" / generation_id
    generated_root = project_root / "generations" / generation_id / "generated"
    render_root.mkdir(parents=True, exist_ok=True)
    generated_root.mkdir(parents=True, exist_ok=True)
    gateway = MagicMock()
    gateway.config.tts_preferences = {}
    return MaterialContext(
        project_id="proj-1",
        generation_id=generation_id,
        render_root=render_root,
        generated_root=generated_root,
        gateway=gateway,
        quota=MagicMock(),
        inventory={},
        slot_matches=[],
        storyboard=[
            {
                "slotId": "slot-1",
                "startSec": 0.0,
                "endSec": 2.0,
                "script": "测试口播。",
            }
        ],
        structure={"audio": {}},
        emit_progress=lambda *_args: None,
        register_artifact=lambda artifact_type, uri: {"type": artifact_type, "uri": str(uri)},
        master_narration="测试口播。",
    )


def test_try_reuse_preview_master_wav_copies_when_hash_matches(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    generation_root = ctx.project_root / "generations" / ctx.generation_id
    draft = {"masterNarration": "测试口播。", "narrationVoProfile": None}
    _write_wav(generation_root / "preview" / "master.wav")
    save_narration_preview(
        generation_root,
        {
            "contentHash": narration_content_hash(draft),
            "durationSec": 2.0,
            "wavUri": "preview/master.wav",
            "alignmentMethod": "whisper",
            "sceneTiming": [{"slotId": "slot-1", "startSec": 0.0, "endSec": 2.0}],
            "warnings": [],
        },
    )
    output = ctx.generated_root / "master.wav"
    assert try_reuse_preview_master_wav(ctx, output)
    assert output.is_file()
    assert output.stat().st_size > 0


def test_try_reuse_preview_master_wav_skips_when_hash_differs(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path)
    generation_root = ctx.project_root / "generations" / ctx.generation_id
    _write_wav(generation_root / "preview" / "master.wav")
    save_narration_preview(
        generation_root,
        {
            "contentHash": "sha256:stale",
            "durationSec": 2.0,
            "wavUri": "preview/master.wav",
            "alignmentMethod": "whisper",
            "sceneTiming": [{"slotId": "slot-1", "startSec": 0.0, "endSec": 2.0}],
            "warnings": [],
        },
    )
    output = ctx.generated_root / "master.wav"
    assert not try_reuse_preview_master_wav(ctx, output)
    assert not output.is_file()
