from __future__ import annotations

import io
import struct
import wave
from pathlib import Path

from app.pipelines.narration_scene_timing import canonical_content_hash, save_narration_timing
from app.providers.material_types import MaterialContext


def write_canonical_fixture(
    ctx: MaterialContext,
    *,
    seconds: float = 1.0,
) -> None:
    generation_root = ctx.project_root / "generations" / ctx.generation_id
    wav_path = generation_root / "narration" / "canonical.wav"
    wav_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(wav_path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(24000)
        handle.writeframes(struct.pack("<h", 0) * int(24000 * seconds))

    draft = {
        "masterNarration": ctx.master_narration,
        "narrationVoProfile": ctx.narration_vo_profile,
        "storyboard": list(ctx.storyboard),
    }
    save_narration_timing(
        generation_root,
        {
            "role": "canonical",
            "contentHash": canonical_content_hash(
                draft,
                structure=ctx.structure,
                workbench_prefs=ctx.gateway.config.tts_preferences,
                generation_id=ctx.generation_id,
            ),
            "durationSec": round(seconds, 3),
            "wavUri": "narration/canonical.wav",
            "alignmentMethod": "whisper",
            "sceneTiming": [
                {
                    "slotId": str(scene.get("slotId") or ""),
                    "startSec": float(scene.get("startSec", 0.0)),
                    "endSec": float(scene.get("endSec", seconds)),
                }
                for scene in ctx.storyboard
                if isinstance(scene, dict) and scene.get("slotId")
            ]
            or [{"slotId": "slot-hook", "startSec": 0.0, "endSec": seconds}],
            "warnings": [],
        },
    )


def wav_bytes(*, seconds: float = 0.1) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(24000)
        handle.writeframes(struct.pack("<h", 0) * int(24000 * seconds))
    return buffer.getvalue()
