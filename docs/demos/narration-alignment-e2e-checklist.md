# Narration / Subtitle / Timeline Alignment E2E Checklist

Prerequisites: API + worker + web running; Model Gateway **tts** provider configured (e.g. volcengine Seed TTS 2.0 or DashScope CosyVoice); optional Pexels for B-roll.

## Generation (global TTS, all durations)

- [ ] Brief includes `durationTarget` and explicit `aspectRatio`
- [ ] Approve master + storyboard (human review) or `VIDEOMAKER_HUMAN_REVIEW_MODE=false` for CI
- [ ] After **master approval**, task stages include `synthesizing_narration_preview` → `aligning_narration_timing` before `drafting_storyboard`
- [ ] `generations/{id}/narration-preview.json` exists with `sceneTiming[]` summing to `durationSec`; `preview/master.wav` playable
- [ ] Storyboard review UI shows preview duration + audio player; scene `startSec/endSec` match `narration-preview.json`
- [ ] After planning, open `generations/{id}/script-draft.json` (if human review):
  - [ ] Optional root `narrationVoProfile` (pace/energy/persona/contextHint)
  - [ ] Storyboard scenes may include optional `voDirective` (Hook/CTA encouraged)
- [ ] After material stage, open `generations/{id}/generation-plan.json`:
  - [ ] `generationStrategy: "long_form_composed"`
  - [ ] `ttsMode: "global"`
  - [ ] `narrationVoProfile` / scene `voDirective` copied from approved script when present
  - [ ] `voiceover` track: **one** clip `vo-master`, `sourceRef: materials/master.wav`
  - [ ] `narrationDurationSec` present and ≈ ffprobe duration of `master.wav`
  - [ ] `timeline.durationSec >= narrationDurationSec`
  - [ ] Subtitles: `subtitle-master-*` clips; last `endSec` ≈ `narrationDurationSec`
- [ ] Play `renders/{id}/output.mp4`: voiceover **not cut** at scene changes; subtitles **track speech** (no obvious lead/lag)
- [ ] Workbench result: variant shows「口播 全片」; if narration > target, amber duration hint

## VO directive → TTS (volcengine)

- [ ] Configure volcengine TTS with expressive model + `ttsPreferences` baseline
- [ ] Run generation where storyboard_writer outputs different `voDirective` on Hook vs CTA (e.g. fast vs slow)
- [ ] Worker uses segmented synthesis when directives differ (multiple gateway calls); single call when all scenes match
- [ ] Listen: Hook vs CTA pacing/energy audibly distinct when directives differ
- [ ] openai_compatible TTS driver: material stage emits `tts_directive_ignored` once; voice still synthesizes

## Layer 2 incremental (reuse visuals)

- [ ] Existing generation has `storyboard` + `generated/slot*.mp4` or stock clips under `materials/`
- [ ] Run `services/worker/scripts/rerun_tts_subtitle_render.py` with project/generation ids
- [ ] `generated/master.wav` refreshed
- [ ] New `output.mp4` overwrites render folder; duration matches narration (~3 min for ~180s script)

## Timeline modes

- [ ] Default `VIDEOMAKER_NARRATION_TIMELINE_MODE=hold_tail` extends last scene when narration > planned duration
- [ ] `global_ripple` or preview/final deviation >3% proportionally rescales all scene windows (global TTS)
- [ ] Material stage reuses `preview/master.wav` when content hash matches (skip duplicate TTS API call)
- [ ] Worker logs may show WAV header fallback warning for DashScope — timeline still correct

## Unit tests

```powershell
cd services/worker
python -m pytest tests/test_narration_alignment.py tests/test_narration_timeline.py tests/test_narration_scene_timing.py tests/test_tts_preview_reuse.py tests/test_tts_subtitle_integration.py tests/test_tts_voice_options.py tests/test_tts_synthesis.py -q
cd ../composition
python -m pytest tests/test_author_payload.py -q
```
