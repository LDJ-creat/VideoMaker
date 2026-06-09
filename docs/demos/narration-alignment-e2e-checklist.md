# Narration / Subtitle / Timeline Alignment E2E Checklist

Prerequisites: API + worker + web running; Model Gateway **tts** provider configured (e.g. DashScope `sambert-zhide-v1`); optional Pexels for B-roll.

## Generation (global TTS, all durations)

- [ ] Brief includes `durationTarget` and explicit `aspectRatio`
- [ ] Approve master + storyboard (human review) or `VIDEOMAKER_HUMAN_REVIEW_MODE=false` for CI
- [ ] After material stage, open `generations/{id}/generation-plan.json`:
  - [ ] `generationStrategy: "long_form_composed"`
  - [ ] `ttsMode: "global"` (unless `VIDEOMAKER_TTS_MODE=per_scene`)
  - [ ] `voiceover` track: **one** clip `vo-master`, `sourceRef: materials/master.wav`
  - [ ] `narrationDurationSec` present and ≈ ffprobe duration of `master.wav`
  - [ ] `timeline.durationSec >= narrationDurationSec`
  - [ ] Subtitles: `subtitle-master-*` clips; last `endSec` ≈ `narrationDurationSec`
- [ ] Play `renders/{id}/output.mp4`: voiceover **not cut** at scene changes; subtitles **track speech** (no obvious lead/lag)
- [ ] Workbench result: variant shows「口播 全片」; if narration > target, amber duration hint

## Layer 2 incremental (reuse visuals)

- [ ] Existing generation has `storyboard` + `generated/slot*.mp4` or stock clips under `materials/`
- [ ] Run `services/worker/scripts/rerun_tts_subtitle_render.py` with project/generation ids
- [ ] `generated/master.wav` created (global) or slot wavs refreshed (per_scene)
- [ ] New `output.mp4` overwrites render folder; duration matches narration (~3 min for ~180s script)

## Optional per-scene TTS override

- [ ] `VIDEOMAKER_TTS_MODE=per_scene` → `ttsMode: "per_scene"` and multiple `vo-{slotId}` clips
- [ ] Subtitles `subtitle-{slotId}-*` aligned within each vo window when per_scene enabled
- [ ] `VIDEOMAKER_NARRATION_TIMELINE_MODE=ripple_overflow` extends per-scene slots when WAV > scene window (per_scene only)
- [ ] Worker logs may show WAV header fallback warning for DashScope — timeline still correct

## Unit tests

```powershell
cd services/worker
python -m pytest tests/test_narration_alignment.py tests/test_narration_timeline.py tests/test_tts_subtitle_integration.py -q
```
