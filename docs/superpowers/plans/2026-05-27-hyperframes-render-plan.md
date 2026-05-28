# HyperFrames Render Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a render backend that converts `RenderTimeline` into a HyperFrames preview composition and, when the CLI is available, an MP4 output.

**Architecture:** Keep rendering behind a `RenderBackend` interface. The P0 backend must always generate a `preview.html` even when MP4 rendering is unavailable, and must return retryable tool errors instead of crashing on missing CLI dependencies.

**Tech Stack:** Python 3.11, pytest, HyperFrames CLI optional, shared `RenderTimeline` contract.

---

## Render Contract

Input is a `RenderTimeline` artifact:

```json
{
  "durationSec": 12,
  "tracks": [
    {"id": "video", "type": "video", "clips": [{"id": "v1", "startSec": 0, "endSec": 3, "sourceRef": "asset-1"}]},
    {"id": "text", "type": "text", "clips": [{"id": "t1", "startSec": 0, "endSec": 3, "content": "Hook"}]}
  ]
}
```

Output artifacts:

- `composition/index.html`: deterministic HyperFrames-compatible preview composition.
- `composition/timeline.json`: copy of normalized `RenderTimeline` used for render.
- `preview.html`: browser-openable preview entry.
- `output.mp4`: optional, only when HyperFrames CLI render succeeds.
- `render-log.json`: command, duration, status, and retryable errors if render fails.

## Timeline To HTML Mapping

The preview composition must be deterministic and seekable:

1. Normalize clips by sorting tracks in contract order: `video`, `image`, `text`, `effect`, `transition`, `voiceover`, `bgm`.
2. Sort clips by `startSec`, then `id`.
3. Convert seconds to milliseconds with `Math.round(sec * 1000)` when writing data attributes.
4. Generate one absolutely positioned DOM node per visual clip with:

```html
data-track="text"
data-start-ms="0"
data-end-ms="3000"
```

5. Use CSS to hide clips outside the current time. The preview page must include a small deterministic script exposing:

```js
window.__videomakerSeek(ms)
window.__videomakerTimeline
```

6. Text clips render as styled caption/title-card layers.
7. Image clips render as `<img>`.
8. Video clips render as muted `<video>` elements and seek relative to clip start.
9. Effect clips render as CSS classes such as `effect-pulse`, `effect-highlight`, or `effect-none`.
10. Transition clips render as overlay layers such as `fade`, `wipe`, or `cut`; unknown transitions degrade to `fade`.

Security rules:

- Escape all text content with HTML escaping.
- Reject `sourceRef` values that resolve outside the project render directory.
- Do not inline arbitrary scripts from model or user content.

## HyperFrames CLI Behavior

The CLI adapter must be optional:

- Detect CLI with `npx hyperframes --version` or configured command runner.
- If unavailable, return `{ok:false,error:{code:"hyperframes_missing",retryable:true}}` and keep preview artifacts.
- If available, render MP4 from the generated composition directory to `output.mp4`.
- Capture stdout/stderr into `render-log.json`.

Default render command shape:

```powershell
npx hyperframes render <composition-dir> --output <output.mp4>
```

If actual CLI syntax differs in the installed version, the implementation must isolate that in `HyperFramesTool` tests and not leak CLI details into `hyperframes_backend.py`.

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
- [ ] Implement HTML generation for image/video/text/effect/transition tracks using the mapping rules specified above.
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
- [ ] Persist `render-log.json` for both success and failure.
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

## Acceptance Criteria

- A fixture `RenderTimeline` renders to deterministic `index.html`, `timeline.json`, and `preview.html`.
- Text content is HTML-escaped in tests.
- Missing HyperFrames CLI produces a retryable tool error and still leaves preview artifacts.
- The backend emits `building_timeline`, `rendering`, and `completed` progress events in order.
- `GenerationPlan.timeline` from the Agent plan can be rendered without transformation beyond path resolution.

## Verification

Run before handoff:

```powershell
cd services/worker
python -m pytest
python -m compileall app
```

If HyperFrames CLI is available, also run one manual preview/render smoke test and record the command output in the handoff.
