# FFmpeg Render Backend E2E Checklist

Prerequisites: API + worker + web; FFmpeg on PATH; Model Gateway TTS configured.

## Default FFmpeg render

- [ ] Fresh generation (>60s long_form) completes render stage without HyperFrames CLI for final MP4
- [ ] `renders/{generationId}/output.mp4` exists and plays in workbench
- [ ] `renders/{generationId}/preview.html` still loads timeline iframe preview
- [ ] `render-log.json` shows `"backend": "ffmpeg"` and stage timings

## Narration alignment (regression)

- [ ] Global TTS: voiceover not cut at scene boundaries; subtitles track speech
- [ ] `timeline.durationSec >= narrationDurationSec` when hold_tail applies
- [ ] Re-run `rerun_tts_subtitle_render.py` produces new MP4 via FFmpeg backend

## Fallback

- [ ] `VIDEOMAKER_RENDER_BACKEND=hyperframes` restores HyperFrames final render
- [ ] Timeline with `effect` track clips auto-fallbacks to hyperframes when env is unset default ffmpeg + capability detect

## Performance

- [ ] ~180s video final render completes in **under ~5 minutes** wall time (vs prior HF 10–30+ min)

## Unit tests

```powershell
cd services/worker
python -m pytest tests/test_resolve_render_backend.py tests/test_ffmpeg_backend.py `
  tests/test_timeline_compiler_segments.py tests/test_subtitle_ass.py tests/test_hold_tail_pad.py -q
```
