# Worker Video Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the worker-side sample video analysis pipeline that produces metadata, audio, transcript, shot boundaries, keyframes, and progress events for downstream structure extraction.

**Architecture:** Implement a local Python worker module under `services/worker` that writes artifacts under `storage/projects/{projectId}` and reports progress through the existing API task event endpoint. Tool adapters must degrade cleanly when optional binaries or models are missing.

**Tech Stack:** Python 3.11, pytest, FFmpeg subprocess, OpenCV optional adapter, fast-whisper optional adapter, existing API `TaskEvent` contract.

---

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

- [ ] Write failing tests for project-scoped artifact paths and path traversal rejection.
- [ ] Implement `TaskContext(project_id, task_id, storage_root, api_base_url=None)`.
- [ ] Implement worker `ArtifactStore` with the same storage safety rule as API: all paths must stay under `storage/projects/{projectId}`.
- [ ] Run `python -m pytest`.
- [ ] Commit: `feat(worker): add runtime and artifact store`.

## Task 2: FFmpeg Adapter

**Files:**
- Create: `services/worker/app/tools/ffmpeg_tool.py`
- Create: `services/worker/tests/test_ffmpeg_tool.py`

- [ ] Write failing tests using a fake command runner for metadata extraction and audio extraction.
- [ ] Implement `FFmpegTool.probe(video_path)` returning duration, width, height, fps, codec, and hasAudio when ffprobe is available.
- [ ] Implement `FFmpegTool.extract_audio(video_path, output_path)`.
- [ ] Return a retryable `ToolError`-like dict when ffmpeg/ffprobe is unavailable instead of crashing.
- [ ] Run `python -m pytest`.
- [ ] Commit: `feat(worker): add ffmpeg adapter`.

## Task 3: Shot Detection And Keyframes

**Files:**
- Create: `services/worker/app/tools/opencv_tool.py`
- Create: `services/worker/tests/test_opencv_tool.py`

- [ ] Write failing tests for deterministic fallback shot boundaries on a missing/unreadable video.
- [ ] Implement `OpenCVTool.detect_shots(video_path)` using frame histogram difference when OpenCV is installed.
- [ ] Implement `OpenCVTool.extract_keyframes(video_path, shots, output_dir)`.
- [ ] Provide a safe fallback result with one full-duration shot when OpenCV cannot process the file.
- [ ] Run `python -m pytest`.
- [ ] Commit: `feat(worker): add shot detection and keyframe extraction`.

## Task 4: Whisper Adapter

**Files:**
- Create: `services/worker/app/tools/whisper_tool.py`
- Create: `services/worker/tests/test_whisper_tool.py`

- [ ] Write failing tests that verify missing `fast_whisper` returns a retryable error object.
- [ ] Implement `WhisperTool.transcribe(audio_path)` with lazy import of `fast_whisper`.
- [ ] Normalize transcript segments into JSON-friendly `{startSec,endSec,text,confidence}` records.
- [ ] Run `python -m pytest`.
- [ ] Commit: `feat(worker): add whisper transcription adapter`.

## Task 5: Sample Pipeline

**Files:**
- Create: `services/worker/app/pipelines/sample_pipeline.py`
- Create: `services/worker/tests/test_sample_pipeline.py`

- [ ] Write failing tests with fake tool adapters proving the pipeline emits ordered stages: `extracting_metadata`, `extracting_audio`, `transcribing`, `detecting_shots`, `extracting_keyframes`, `completed`.
- [ ] Implement `SampleAnalysisPipeline.run(project_id, task_id, video_path)`.
- [ ] Persist artifacts: `metadata.json`, `audio.wav` when available, `transcript.json`, `shots.json`, and `keyframes/`.
- [ ] Return a summary object containing artifact refs and the final task event.
- [ ] Run `python -m pytest`.
- [ ] Commit: `feat(worker): add sample analysis pipeline`.

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

