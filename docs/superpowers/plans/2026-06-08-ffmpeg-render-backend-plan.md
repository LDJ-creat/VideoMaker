# FFmpeg Render Backend Plan

**Date:** 2026-06-08  
**Status:** Implemented

## Summary

Final MP4 delivery uses **FFmpeg** (`FfmpegRenderBackend`) by default instead of whole-timeline HyperFrames frame capture. **HyperFrames remains** for slot-level `hyperframes_material` and HTML `preview.html`. Narration/subtitle/timeline alignment ([narration-alignment plan](./2026-06-08-narration-alignment-plan.md)) is unchanged — FFmpeg consumes aligned `RenderTimeline` only.

## Architecture

```text
hyperframes_material / AIGC / stock / TTS
  → RenderTimeline
  → sync_timeline_to_narration + align_subtitles_to_voiceover
  → resolve_render_backend (auto: ffmpeg; hyperframes when effect/packaging text)
  → preview.html (write_composition) + output.mp4 (FfmpegRenderBackend)
```

| Layer | Component | Output |
|-------|-----------|--------|
| Slot material | `HyperFramesMaterialTool` | `{slotId}.mp4` |
| Alignment | `narration_timeline`, `narration_alignment` | aligned timeline |
| Preview | `composition_preview` | `preview.html` |
| Final MP4 | `FfmpegRenderBackend` | `output.mp4` |
| Fallback | `HyperFramesRenderBackend` | `VIDEOMAKER_RENDER_BACKEND=hyperframes` |

## Modules

| Path | Role |
|------|------|
| `app/render/resolve_render_backend.py` | Backend routing + `build_render_backend()` |
| `app/render/composition_preview.py` | Shared preview HTML |
| `app/render/ffmpeg_backend.py` | FFmpeg render backend |
| `app/render/timeline_compiler/` | Timeline → staged ffmpeg pipeline |
| `app/tools/ffmpeg_tool.py` | Extended trim/concat/scale/ass/mix |

## Env (worker)

| Variable | Default | Meaning |
|----------|---------|---------|
| `VIDEOMAKER_RENDER_BACKEND` | unset (auto) | `ffmpeg`, `hyperframes`, or unset — auto picks ffmpeg unless timeline needs live HTML (effect track / non-subtitle packaging text) |
| `VIDEOMAKER_FFMPEG_RENDER_FPS` | `30` | FPS for still→video and re-encode |
| `VIDEOMAKER_FFMPEG_VIDEO_CRF` | `23` | libx264 quality |
| `VIDEOMAKER_FFMPEG_BGM_VOLUME` | `0.25` | BGM mix level |
| `VIDEOMAKER_FFMPEG_TRANSITION_MODE` | `cut` | `cut`, `overlay_fade`, or `xfade` |

## Transitions

- **v1 / cut:** hard concat at scene boundaries
- **overlay_fade / xfade:** segment-boundary fades (does not recompute subtitle/vo timestamps)

## Verification

```powershell
cd services/worker
python -m pytest tests/test_resolve_render_backend.py tests/test_timeline_compiler_segments.py `
  tests/test_subtitle_ass.py tests/test_hold_tail_pad.py tests/test_ffmpeg_backend.py `
  tests/test_narration_alignment.py tests/test_narration_timeline.py -q
```

Manual: `docs/demos/ffmpeg-render-e2e-checklist.md`, `docs/demos/narration-alignment-e2e-checklist.md`.

## Files

| Area | Key paths |
|------|-----------|
| Backend | `ffmpeg_backend.py`, `resolve_render_backend.py`, `composition_preview.py` |
| Compiler | `timeline_compiler/compile.py`, `scene_segments.py`, `video_builder.py`, `subtitle_ass.py`, `audio_mixer.py`, `hold_tail.py`, `transition_map.py` |
| Integration | `p0_demo_pipeline.py`, `scripts/rerun_tts_subtitle_render.py` |
| API | `generation_responses.py` (docstring only) |
