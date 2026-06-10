from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from app.pipelines.narration_scene_timing import (
    load_narration_preview,
    narration_content_hash,
    preview_wav_path,
    storyboard_scripts_match_master,
)
from app.pipelines.tts_synthesis import _scenes_with_script
from app.pipelines.tts_voice_options import build_tts_synthesis_options, canonical_tts_options_key
from app.providers.material_types import MaterialContext


def generation_root_from_ctx(ctx: MaterialContext) -> Path:
    return ctx.project_root / "generations" / ctx.generation_id


def needs_segmented_master_tts(ctx: MaterialContext) -> bool:
    scenes = _scenes_with_script(list(ctx.storyboard))
    if not scenes:
        return False
    keys: set[str] = set()
    for scene in scenes:
        options = build_tts_synthesis_options(
            structure=ctx.structure,
            workbench_prefs=ctx.gateway.config.tts_preferences,
            generation_id=ctx.generation_id,
            narration_vo_profile=ctx.narration_vo_profile,
            scene_vo_directive=(
                scene.get("voDirective") if isinstance(scene.get("voDirective"), dict) else None
            ),
        )
        keys.add(canonical_tts_options_key(options))
    return len(keys) > 1


def try_reuse_preview_master_wav(ctx: MaterialContext, output_path: Path) -> bool:
    if needs_segmented_master_tts(ctx):
        return False
    generation_root = generation_root_from_ctx(ctx)
    preview = load_narration_preview(generation_root)
    if preview is None:
        return False
    draft_hash = narration_content_hash(
        {
            "masterNarration": ctx.master_narration,
            "narrationVoProfile": ctx.narration_vo_profile,
        }
    )
    if preview.get("contentHash") != draft_hash:
        return False
    if not storyboard_scripts_match_master(list(ctx.storyboard), ctx.master_narration):
        return False
    source = preview_wav_path(generation_root)
    if not source.is_file() or source.stat().st_size <= 0:
        return False
    output_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, output_path)
    ctx.emit_progress("tts_preview_reused", "Reused narration preview master.wav")
    return True
