from __future__ import annotations

import shutil
from pathlib import Path

from app.pipelines.narration_scene_timing import (
    canonical_content_hash,
    load_narration_timing,
    narration_timing_is_current,
)
from app.pipelines.tts_synthesis import _scenes_with_script
from app.providers.material_types import MaterialContext
from app.pipelines.canonical_narration import CANONICAL_WAV_REL, canonical_wav_path


def generation_root_from_ctx(ctx: MaterialContext) -> Path:
    return ctx.project_root / "generations" / ctx.generation_id


def try_reuse_canonical_master_wav(ctx: MaterialContext, output_path: Path) -> bool:
    generation_root = generation_root_from_ctx(ctx)
    timing = load_narration_timing(generation_root)
    if timing is None or timing.get("role") != "canonical":
        return False

    draft = {
        "masterNarration": ctx.master_narration,
        "narrationVoProfile": ctx.narration_vo_profile,
        "storyboard": list(ctx.storyboard),
    }
    if not narration_timing_is_current(
        generation_root,
        draft,
        structure=ctx.structure,
        workbench_prefs=ctx.gateway.config.tts_preferences,
        generation_id=ctx.generation_id,
    ):
        return False

    source = canonical_wav_path(generation_root)
    if not source.is_file() or source.stat().st_size <= 0:
        alt = generation_root / str(timing.get("wavUri") or CANONICAL_WAV_REL)
        source = alt if alt.is_file() else source
    if not source.is_file() or source.stat().st_size <= 0:
        return False

    output_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, output_path)
    ctx.emit_progress("canonical_tts_reused", "Reused canonical narration master.wav")
    return True


def needs_segmented_master_tts(ctx: MaterialContext) -> bool:
    """Legacy helper retained for tests; canonical path always allows reuse when current."""
    scenes = _scenes_with_script(list(ctx.storyboard))
    return len(scenes) > 1
