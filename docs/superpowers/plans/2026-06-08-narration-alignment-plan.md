# Narration / Subtitle / Timeline Alignment Plan

**Date:** 2026-06-08  
**Status:** Implemented

## Summary

Fixes voiceover truncation at scene cuts and subtitle–audio desync by aligning subtitles to audible WAV windows, introducing **global TTS** for long-form generations, and extending the timeline when narration exceeds the planned storyboard duration.

## Problems (before)

| Symptom | Root cause |
|---------|------------|
| Subtitles appear faster than voiceover | Subtitles scheduled inside `[scene.startSec, scene.endSec]` by **character weight**; TTS uses **WAV duration** |
| Voiceover cut off at scene boundaries | Per-scene `vo-{slotId}` clips end at `min(storyboard_end, start+wav)`; HyperFrames GSAP `pause()` at `endSec` |
| Long videos (~180s) worst affected | Many scenes × per-scene TTS; cumulative truncation |

## Architecture (after)

```text
masterNarration (approved script)
  → resolve_tts_mode (global | per_scene)
  → TTS (master.wav OR slot*.wav)
  → apply_material_results_to_plan
      → sync_timeline_to_narration   # hold_tail / ripple_overflow
      → align_subtitles_to_voiceover # rebuild subtitle-* from vo window
  → HyperFrames render (single vo-master play/pause for global)
```

### Phase 1 — Subtitle ↔ voiceover alignment

**Module:** `services/worker/app/pipelines/narration_alignment.py`

- `align_subtitles_to_voiceover`: after material completion, strip placeholder `subtitle-*` clips and rebuild from **voiceover audible window** (`vo.startSec` … `vo.endSec`), using the same sentence chunking as assemble.
- `wav_duration_sec`: reads WAV length; **falls back to file-size estimate** when RIFF headers are corrupt (DashScope `sambert` sometimes reports bogus `nframes`).
- Wired in `completion_registry.apply_material_results_to_plan` (always runs post-TTS).

### Phase 2 — Global TTS

**Module:** `services/worker/app/pipelines/tts_mode.py`

| `VIDEOMAKER_TTS_MODE` | Behavior |
|-----------------------|----------|
| `global` | Single `action-master-tts` → `generated/master.wav` → one `vo-master` clip |
| `per_scene` | Legacy `{slotId}.wav` per storyboard scene |
| *(unset)* | Default **`global`** (all durations use `long_form_composed`; legacy per-scene plans keep `ttsMode: per_scene` when inferred from completion actions) |

- `TTSProvider`: `slotId == __master__` synthesizes `ctx.master_narration`.
- `assemble_generation_plan`: writes `plan.ttsMode`; skips per-scene placeholder subtitles when global.
- Contracts: optional `GenerationPlan.ttsMode`, `narrationDurationSec`.

### Phase 3 — Timeline vs narration

**Module:** `services/worker/app/pipelines/narration_timeline.py`

| `VIDEOMAKER_NARRATION_TIMELINE_MODE` | Behavior |
|--------------------------------------|----------|
| `hold_tail` (default) | `durationSec = max(planned, narration_end)`; extend **last scene** + last video clip |
| `ripple_overflow` | Per-scene mode only: extend scenes when WAV > slot window; ripple following `startSec`/`endSec` |
| `scale_to_target` | Alias to hold_tail for now |

- If planned duration was inflated by corrupt WAV metadata, `hold_tail` trusts `narration_end` when `planned > narration * 1.25`.
- Render: `render_timeline_to_hyperframes` plays **one** `vo-master` from `t=0` to `timeline.durationSec` (no per-clip `currentTime=0` reset).

## Material completion order

```text
_apply_generated_sources_to_timeline
  → sync_timeline_to_narration
  → align_subtitles_to_voiceover
```

## Incremental re-run (Layer 2 testing)

Without re-running LLM / Pexels / AIGC video:

```powershell
cd services/worker
python scripts/rerun_tts_subtitle_render.py `
  --project-id <projectId> `
  --generation-id <generationId> `
  --storage-root d:\VideoMaker\services\api\storage `
  --database-path d:\VideoMaker\services\api\storage\videomaker.sqlite3
```

- `--skip-tts`: reuse existing `master.wav` / `slot*.wav`; still runs timeline sync + subtitle align + render.
- Deletes prior TTS wav artifacts before re-synthesis when TTS is not skipped.

## Env (worker)

| Variable | Default | Meaning |
|----------|---------|---------|
| `VIDEOMAKER_TTS_MODE` | strategy-based | `global` or `per_scene` |
| `VIDEOMAKER_NARRATION_TIMELINE_MODE` | `hold_tail` | Timeline extension strategy |

Documented in root `AGENTS.md`.

## Web

- `GenerationResultView`: shows `ttsMode` label; amber banner when `narrationDurationSec > durationTargetSec`.

## Verification

```powershell
cd services/worker
python -m pytest tests/test_narration_alignment.py tests/test_narration_timeline.py `
  tests/test_generation_plan.py tests/test_completion_registry.py `
  tests/test_timeline_to_hyperframes.py tests/test_tts_subtitle_integration.py
```

Manual: `docs/demos/narration-alignment-e2e-checklist.md`, P1 guide § G6/G6b.

## Files

| Area | Key paths |
|------|-----------|
| Alignment | `narration_alignment.py` |
| Timeline | `narration_timeline.py` |
| TTS mode | `tts_mode.py`, `tts_provider.py` |
| Integration | `completion_registry.py`, `generation_pipeline.py` |
| Render | `render_timeline_to_hyperframes.py` |
| Ops script | `scripts/rerun_tts_subtitle_render.py` |
| Contracts | `generation-plan.schema.json`, `types.ts` |

## Known provider quirk

DashScope-compatible TTS may return WAV with valid PCM payload but **invalid `nframes` in the header**. `wav_duration_sec` detects header vs payload mismatch (>25%) and uses byte-size duration. Logs: `WAV header duration … exceeds payload estimate … using size estimate`.
