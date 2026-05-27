# HyperFrames Render Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a render backend that converts `RenderTimeline` into a HyperFrames preview composition and, when the CLI is available, an MP4 output.

**Architecture:** Keep rendering behind a `RenderBackend` interface. The P0 backend must always generate a `preview.html` even when MP4 rendering is unavailable, and must return retryable tool errors instead of crashing on missing CLI dependencies.

**Tech Stack:** Python 3.11, pytest, HyperFrames CLI optional, shared `RenderTimeline` contract.

---

## Scope And Boundaries

Branch/worktree:

```powershell
git worktree add .worktrees/hyperframes-render -b feature/hyperframes-render main
```

Allowed to create/modify:

- `services/worker/app/render/**`
- `services/worker/app/tools/hyperframes_tool.py`
- `services/worker/tests/**`
- `docs/superpowers/plans/2026-05-27-hyperframes-render-plan.md`

Do not modify:

- `packages/contracts/**`
- `apps/web/**`
- `services/api/**`

## Task 1: Render Backend Interface

**Files:**
- Create: `services/worker/app/render/backend.py`
- Create: `services/worker/tests/test_render_backend.py`

- [ ] Write failing tests for a backend returning preview and optional video artifact refs.
- [ ] Define `RenderOptions`, `RenderOutput`, and `RenderBackend` protocol/classes.
- [ ] Keep output JSON-friendly and compatible with `ArtifactRef`.
- [ ] Run `python -m pytest`.
- [ ] Commit: `feat(render): add render backend interface`.

## Task 2: Timeline To HyperFrames Composition

**Files:**
- Create: `services/worker/app/render/render_timeline_to_hyperframes.py`
- Create: `services/worker/tests/fixtures/render_timeline.json`
- Create: `services/worker/tests/test_timeline_to_hyperframes.py`

- [ ] Write failing tests that generate `index.html` from a fixture `RenderTimeline`.
- [ ] Implement HTML generation for image/video/text/effect/transition tracks.
- [ ] Escape text content and asset paths safely.
- [ ] Ensure generated preview contains stable timeline metadata for debugging.
- [ ] Run `python -m pytest`.
- [ ] Commit: `feat(render): convert timeline to hyperframes preview`.

## Task 3: HyperFrames Tool

**Files:**
- Create: `services/worker/app/tools/hyperframes_tool.py`
- Create: `services/worker/tests/test_hyperframes_tool.py`

- [ ] Write failing tests with a fake command runner for CLI present and missing CLI cases.
- [ ] Implement `HyperFramesTool.render(composition_dir, output_path)`.
- [ ] Return retryable error when CLI is unavailable.
- [ ] Do not delete preview artifacts when MP4 render fails.
- [ ] Run `python -m pytest`.
- [ ] Commit: `feat(render): add hyperframes cli adapter`.

## Task 4: Render Pipeline

**Files:**
- Create: `services/worker/app/render/hyperframes_backend.py`
- Create: `services/worker/tests/test_hyperframes_backend.py`

- [ ] Write failing tests for rendering a timeline fixture to `preview.html`.
- [ ] Implement backend that writes composition files under `storage/projects/{projectId}/renders/{generationId}`.
- [ ] Emit progress stages: `building_timeline`, `rendering`, `completed`.
- [ ] Register preview and MP4 artifacts when available.
- [ ] Run `python -m pytest`.
- [ ] Commit: `feat(render): add hyperframes render backend`.

## Verification

Run before handoff:

```powershell
cd services/worker
python -m pytest
python -m compileall app
```

If HyperFrames CLI is available, also run one manual preview/render smoke test and record the command output in the handoff.

