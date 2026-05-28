# Worker Video Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the worker-side sample video analysis pipeline that produces metadata, audio, transcript, shot boundaries, keyframes, and progress events for downstream structure extraction.

**Architecture:** Implement a local Python worker module under `services/worker` that writes artifacts under `storage/projects/{projectId}` and reports progress through the existing API task event endpoint. Tool adapters must degrade cleanly when optional binaries or models are missing.

**Tech Stack:** Python 3.11, pytest, FFmpeg subprocess, OpenCV optional adapter, fast-whisper optional adapter, existing API `TaskEvent` contract.

---

## Required P0 Outputs

The worker must produce these artifacts for one sample video:

- `metadata.json`: duration, width, height, fps, video codec, audio codec, hasAudio, source path.
- `audio.wav`: 16 kHz mono PCM extracted with FFmpeg when audio exists.
- `transcript.json`: ASR segments normalized as `{startSec,endSec,text,confidence}`.
- `shots.json`: shot boundaries normalized as `{startSec,endSec,confidence,changeReason}`.
- `keyframes/shot-{index}-{timeMs}.jpg`: one representative keyframe per shot.
- `sample-analysis.json`: consolidated object consumed by `structure_pipeline`.

The worker must emit these `TaskEvent.stage` values in order:

```text
extracting_metadata
extracting_audio
transcribing
detecting_shots
extracting_keyframes
completed
```

## Tool Collaboration

The sample pipeline coordinates tools in this order:

```text
Input video path or downloaded URL artifact
-> FFmpegTool.probe
-> FFmpegTool.extract_audio
-> WhisperTool.transcribe
-> OpenCVTool.detect_shots
-> OpenCVTool.extract_keyframes
-> SampleAnalysisPipeline writes sample-analysis.json
-> TaskContext registers artifacts and emits progress
```

Each tool must be independently testable. The pipeline must accept fake tool adapters in tests so an implementation agent can verify behavior without requiring FFmpeg, OpenCV, or fast-whisper to be installed.

## Shot Detection Algorithm

Implement deterministic P0 shot detection with OpenCV when available:

1. Open video with `cv2.VideoCapture` and read `fps`, frame count, and duration.
2. Sample frames at a maximum of 3 fps for analysis, even if the source video has a higher frame rate.
3. Convert sampled frames to HSV and compute a normalized histogram using H and S channels.
4. Compute histogram distance between adjacent sampled frames with `1 - cv2.compareHist(prev, curr, cv2.HISTCMP_CORREL)`.
5. Compute an adaptive threshold: `median(distance) + 3 * MAD(distance)`, clamped to `[0.35, 0.75]`.
6. Mark a cut when distance exceeds threshold and the previous boundary is at least `minShotDurationSec = 0.45` earlier.
7. Merge shots shorter than `0.35s` into the previous shot.
8. If no cuts are detected, return one full-duration shot with `changeReason = "unknown"` and `confidence = 0.4`.

Confidence rule:

```text
confidence = min(1.0, max(0.45, distance / threshold))
```

Fallback behavior:

- If OpenCV cannot import or the file cannot be opened, return one full-duration shot and a retryable tool warning.
- Do not crash the pipeline only because shot detection is weak.

## Keyframe Selection Algorithm

Extract one keyframe per detected shot:

1. For each shot, sample candidate frames at 20%, 50%, and 80% of the shot duration.
2. For shots shorter than 0.8s, sample only the midpoint.
3. Score each candidate with:

```text
sharpness = variance(Laplacian(gray))
entropy = grayscale histogram entropy
exposurePenalty = abs(meanBrightness - 128) / 128
score = normalize(sharpness) * 0.6 + normalize(entropy) * 0.3 - exposurePenalty * 0.1
```

4. Choose the highest-scoring candidate.
5. Write JPEG at quality 88 to `keyframes/shot-{index}-{timeMs}.jpg`.
6. If all candidate reads fail, seek to the shot midpoint and write that frame if possible.

The output `keyframes.json` must record `{shotId, timeSec, path, score, width, height}` for each keyframe. `sample-analysis.json` should reference both `shots.json` and `keyframes.json`.

## URL Download Scope

The worker owns URL media download through `YtDlpTool`; the frontend only submits a URL and shows progress. P0 must support direct video URLs and common short-video/web URLs through `yt-dlp` when installed.

Download rules:

- Tool file: `services/worker/app/tools/ytdlp_tool.py`
- Output path: `storage/projects/{projectId}/samples/{sampleId}/original.{ext}`
- Maximum duration default: 180 seconds.
- Maximum file size default: 500 MB.
- Allowed extensions: `mp4`, `mov`, `mkv`, `webm`.
- On missing `yt-dlp`, return retryable error `{code:"ytdlp_missing", retryable:true}`.
- On unsupported URL or oversize video, return non-retryable error with a clear code.

## Scope And Boundaries

Branch/worktree:

```powershell
git worktree add .worktrees/worker-video-analysis -b feature/worker-video-analysis main
```

Allowed to create/modify:

- `services/worker/**`
- `docs/superpowers/plans/2026-05-27-worker-video-analysis-plan.md`

Do not modify:

- `packages/contracts/**`
- `services/api/**` except if a small integration fixture is explicitly needed and reviewed first
- `apps/web/**`

## Task 1: Worker Package And Runtime

**Files:**
- Create: `services/worker/pyproject.toml`
- Create: `services/worker/app/__init__.py`
- Create: `services/worker/app/runtime/task_context.py`
- Create: `services/worker/app/runtime/artifact_store.py`
- Create: `services/worker/tests/test_runtime.py`

- [x] Write failing tests for project-scoped artifact paths and path traversal rejection.
- [x] Implement `TaskContext(project_id, task_id, storage_root, api_base_url=None)`.
- [x] Implement worker `ArtifactStore` with the same storage safety rule as API: all paths must stay under `storage/projects/{projectId}`.
- [x] Run `python -m pytest`.
- [x] Commit: `feat(worker): add runtime and artifact store`.

## Task 2: FFmpeg Adapter

**Files:**
- Create: `services/worker/app/tools/ffmpeg_tool.py`
- Create: `services/worker/tests/test_ffmpeg_tool.py`

- [x] Write failing tests using a fake command runner for metadata extraction and audio extraction.
- [x] Implement `FFmpegTool.probe(video_path)` returning duration, width, height, fps, codec, and hasAudio when ffprobe is available.
- [x] Implement `FFmpegTool.extract_audio(video_path, output_path)`.
- [x] Return a retryable `ToolError`-like dict when ffmpeg/ffprobe is unavailable instead of crashing.
- [x] Run `python -m pytest`.
- [x] Commit: `feat(worker): add ffmpeg adapter`.

## Task 3: YtDlp URL Download Adapter

**Files:**
- Create: `services/worker/app/tools/ytdlp_tool.py`
- Create: `services/worker/tests/test_ytdlp_tool.py`

- [x] Write failing tests with a fake command runner for successful URL download, missing `yt-dlp`, oversize rejection, and unsupported extension rejection.
- [x] Implement `YtDlpTool.download(url, output_dir, max_duration_sec=180, max_file_size_mb=500)`.
- [x] Use `yt-dlp --dump-json` first to inspect duration, extension, and filesize before downloading when metadata is available.
- [x] Download with `yt-dlp -o <output-template> --no-playlist`.
- [x] Return artifact-ready metadata `{path, durationSec, ext, sourceUrl}`.
- [x] Run `python -m pytest`.
- [x] Commit: `feat(worker): add ytdlp url download adapter`.

## Task 4: Shot Detection And Keyframes

**Files:**
- Create: `services/worker/app/tools/opencv_tool.py`
- Create: `services/worker/tests/test_opencv_tool.py`

- [x] Write failing tests for deterministic fallback shot boundaries on a missing/unreadable video.
- [x] Implement `OpenCVTool.detect_shots(video_path)` using the HSV histogram/MAD algorithm specified above.
- [x] Implement `OpenCVTool.extract_keyframes(video_path, shots, output_dir)` using the sharpness/entropy/exposure scoring algorithm specified above.
- [x] Persist `shots.json`, `keyframes.json`, and JPEG keyframes.
- [x] Provide a safe fallback result with one full-duration shot when OpenCV cannot process the file.
- [x] Run `python -m pytest`.
- [x] Commit: `feat(worker): add shot detection and keyframe extraction`.

## Task 5: Whisper Adapter

**Files:**
- Create: `services/worker/app/tools/whisper_tool.py`
- Create: `services/worker/tests/test_whisper_tool.py`

- [x] Write failing tests that verify missing `fast_whisper` returns a retryable error object.
- [x] Implement `WhisperTool.transcribe(audio_path)` with lazy import of `fast_whisper`.
- [x] Normalize transcript segments into JSON-friendly `{startSec,endSec,text,confidence}` records.
- [x] Run `python -m pytest`.
- [x] Commit: `feat(worker): add whisper transcription adapter`.

## Task 6: Sample Pipeline

**Files:**
- Create: `services/worker/app/pipelines/sample_pipeline.py`
- Create: `services/worker/tests/test_sample_pipeline.py`

- [x] Write failing tests with fake tool adapters proving the pipeline emits ordered stages: `extracting_metadata`, `extracting_audio`, `transcribing`, `detecting_shots`, `extracting_keyframes`, `completed`.
- [x] Implement `SampleAnalysisPipeline.run(project_id, task_id, video_path=None, source_url=None)`.
- [x] If `source_url` is provided, call `YtDlpTool.download` before metadata extraction and register the downloaded original video.
- [x] Persist artifacts: `metadata.json`, `audio.wav` when available, `transcript.json`, `shots.json`, `keyframes.json`, `keyframes/`, and `sample-analysis.json`.
- [x] Return a summary object containing artifact refs and the final task event.
- [x] Run `python -m pytest`.
- [x] Commit: `feat(worker): add sample analysis pipeline`.

## Acceptance Criteria

- A fake-tool test proves the full pipeline emits all progress stages and writes all expected artifact refs.
- An OpenCV unit test proves two visually different synthetic frames produce a shot boundary.
- A keyframe unit test proves the sharpest candidate is selected from a controlled frame set.
- A missing-tool test proves FFmpeg, OpenCV, fast-whisper, and yt-dlp failures become structured tool errors rather than uncaught exceptions.
- `sample-analysis.json` contains enough data for the Agent module to build `VideoStructure` without rereading video files.

## Verification

Run before handoff:

```powershell
cd services/worker
python -m pytest
python -m compileall app
```

Also run existing foundations from repo root:

```powershell
cd packages/contracts
npm run check
npm run validate:schemas

cd ../../services/api
python -m pytest
```
