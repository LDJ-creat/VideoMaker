# AGENTS.md

## Project Context

VideoMaker is a competition project for an AI short-video creation system. The product goal is a "viral structure migration engine": analyze high-performing sample videos, extract reusable creative structure, map that structure to a new topic or user assets, identify material gaps, and generate an explainable storyboard, timeline, packaging plan, and demo video.

The competition brief is stored in `VideoMaker.md`. The user's original solution sketch is stored in `VideoMakerDesign.md`. The refined project design and implementation plans are the source of truth for development:

- `docs/superpowers/specs/2026-05-27-videomaker-design.md` (architecture spec)
- `docs/superpowers/plans/P0/` (archived P0 implementation plans; see index below)
- `docs/superpowers/plans/2026-05-29-videomaker-p1-implementation-plan.md` (active P1 master plan)

### P0 Plan Archive (`docs/superpowers/plans/P0/`)

| Plan | Purpose |
|------|---------|
| `2026-05-27-videomaker-p0-implementation-plan.md` | Master P0 execution order |
| `2026-05-27-contracts-foundation-plan.md` | Shared schemas and TypeScript types |
| `2026-05-27-api-task-artifacts-plan.md` | FastAPI tasks, SSE, artifacts |
| `2026-05-27-worker-video-analysis-plan.md` | FFmpeg, OpenCV, Whisper, sample pipeline |
| `2026-05-27-web-workbench-plan.md` | Next.js workbench and task progress |
| `2026-05-27-agent-generation-plan.md` | Slot mapping, gap report, generation plan |
| `2026-05-27-hyperframes-render-plan.md` | RenderTimeline → HyperFrames preview |
| `2026-05-27-integration-p0-demo-flow-plan.md` | End-to-end API + worker wiring |
| `2026-05-28-web-workbench-hardening-plan.md` | Workbench persistence and UX hardening |
| `2026-05-28-parallel-agent-prompts.md` | Parallel worktree agent prompts |

Legacy copies may still exist under `docs/superpowers/plans/`; prefer the `P0/` archive for completed work.

## Product Direction

P0 is not a full video editor and not a direct sample-video copier. P0 must demonstrate a stable, explainable core loop:

```text
sample video input
-> video analysis and structure extraction
-> standardized structure slots
-> new brief and user asset analysis
-> slot matching and gap detection
-> completion planning
-> storyboard / render timeline / packaging plan
-> HyperFrames demo and process visualization
```

The key scoring dimensions are:

- clear definition of "video structure"
- explainable structure migration
- material gap detection and completion
- visible migration process
- verifiable output such as storyboard, timeline, or demo video

## P0 Status (merged on `main`)

P0 module work is complete on `main`. The following feature/integration branches were implemented and merged:

- `feature/contracts-foundation`
- `feature/api-task-artifacts`
- `feature/worker-video-analysis`
- `feature/web-workbench`
- `feature/agent-generation`
- `feature/hyperframes-render`
- `integration/p0-demo-flow`

Post-P0 fixes (also on `main`) include checkpoint resume, global cookie upload, project/sample/asset API hydration, workbench result reload (`GET .../generations/latest`), and upload UX improvements.

Demo verification checklist: `docs/demos/p0-demo-checklist.md`.

## P1 Status (in planning)

P1 master plan: `docs/superpowers/plans/2026-05-29-videomaker-p1-implementation-plan.md`.

P1 execution order and per-plan agent prompts: `docs/superpowers/plans/2026-05-29-p1-execution-order-and-prompts.md`.

P1 submodule plans (under `docs/superpowers/plans/2026-05-29-p1-*-plan.md`): contracts extension, ModelGateway, agent orchestration, LLM structure, asset understanding, semantic mapping/gap, AIGC material, HyperFrames material, multi-variant, NL revise, web workbench, observability.

P1 focus: real LLM Agent pipeline (no rule semantic fallback), ModelGateway (OpenAI-compatible text/vision/TTS/image + pluggable video), AIGC material completion, HyperFrames clip-level material generation, default variants `high_click` + `high_conversion`, NL revise. Submodule plans listed in the master plan §3; execute per execution-order doc.

## Current Implementation State

### Contracts (`packages/contracts`)

TypeScript types and JSON Schemas for:

- `ArtifactRef`, `ToolError`, `TaskEvent`
- `VideoStructure`, `AssetInventory`, `GapReport`, `GenerationPlan`, `RenderTimeline`

```powershell
cd packages/contracts
npm run check
npm run validate:schemas
```

### API (`services/api`)

FastAPI app factory: `app.main.create_app`. SQLite metadata in `services/api/storage/videomaker.sqlite3` (gitignored). Runtime artifacts under repo `storage/`.

**Task progress (authoritative in SQLite, SSE + polling on frontend):**

```http
GET /health
POST /api/tasks
GET /api/tasks/{task_id}
POST /api/tasks/{task_id}/events
GET /api/tasks/{task_id}/events
POST /api/tasks/{task_id}/retry
POST /api/tasks/{task_id}/cancel
```

`POST /api/tasks/{task_id}/retry` re-dispatches the worker for the same `task_id` with `resume=true` for sample analysis or generation. Do not create a new analyze task for retries.

**Projects and P0 demo flow:**

```http
GET /api/projects
POST /api/projects
GET /api/projects/{project_id}
GET /api/projects/{project_id}/brief
POST /api/projects/{project_id}/brief
GET /api/projects/{project_id}/assets
POST /api/projects/{project_id}/assets/upload
GET /api/projects/{project_id}/samples
GET /api/projects/{project_id}/samples/active
POST /api/projects/{project_id}/samples/upload
POST /api/projects/{project_id}/samples/from-url
GET /api/projects/{project_id}/media/samples/{sample_id}
GET /api/projects/{project_id}/media/assets/{asset_id}
POST /api/projects/{project_id}/generation-plan
GET /api/projects/{project_id}/generations/latest
GET /api/settings/cookies
POST /api/settings/cookies/upload
GET /api/settings/model-gateway
PUT /api/settings/model-gateway
```

Per-project cookie routes under `/api/projects/{id}/cookies*` are deprecated; use global settings routes.

Model gateway provider credentials (base URL, model, encrypted API key) persist in SQLite table `model_gateway_providers`; encryption key file: `storage/global/model-gateway.key`. `GET` never returns secrets. `fixtureMode` in the response reflects env `VIDEOMAKER_FIXTURE_MODE` only (configure in the API process, not via PUT).

**Samples and generations:**

```http
POST /api/samples/{sample_id}/analyze
GET /api/samples/{sample_id}/structure
GET /api/samples/{sample_id}/analysis
GET /api/generations/{generation_id}
```

Local dev server: `services/api/run-dev.ps1` (or `uvicorn` via project conventions).

```powershell
cd services/api
python -m pytest
python -m compileall app
```

`pyproject.toml` sets pytest `--basetemp=.pytest-tmp` because the default Windows temp path may be inaccessible in this environment.

### Worker (`services/worker`)

Pipelines and tools:

- `SampleAnalysisPipeline` / `p0_demo_pipeline` — metadata, shots, Whisper ASR, deterministic `structure_pipeline`
- `generation_pipeline` — asset inventory, slot mapping, gap report, generation plan
- Tools: `ffmpeg_tool`, `opencv_tool`, `whisper_tool`, `ytdlp_tool`, optional `hyperframes_tool`
- Render: `render_timeline_to_hyperframes`, `hyperframes_backend` (preview under `generations/{generationId}/render/`)

```powershell
cd services/worker
python -m pytest
python -m compileall app
```

### Web (`apps/web`)

Next.js workbench at `/projects` and `/projects/{projectId}`:

- Task progress: SSE primary, polling fallback (`useTaskProgress`)
- Panels: input, progress, analysis, structure slots, gap, timeline, result
- Loads projects, samples, assets, brief, and latest generation from API on mount (not sessionStorage-only)

```powershell
cd apps/web
npm run typecheck
npm run test
npm run dev
```

Fixture fallback when API unreachable: `VIDEOMAKER_USE_FIXTURE_FALLBACK=true` (see `apps/web/lib/server/fixture-resolver.ts`).

### Checkpoint Resume (P0)

Worker pipelines persist stage checkpoints under stable business IDs (not `task_id`):

```text
storage/projects/{projectId}/
  samples/{sampleId}/analysis/checkpoint.json
  generations/{generationId}/checkpoint.json
```

Sample analysis artifacts live in `samples/{sampleId}/analysis/`. Generation stage JSON lives in `generations/{generationId}/`. The frontend retry button calls `POST /api/tasks/{taskId}/retry` and keeps the same SSE/polling task id.

Global yt-dlp cookies: `storage/global/cookies/` (shared across projects).

## Architecture Rules

Use these core contracts as module boundaries:

- `VideoStructure` is the authoritative result of sample structure extraction.
- `AssetInventory` describes the user brief and available materials.
- `GapReport` describes matched, weak, and missing structure slots.
- `GenerationPlan` describes storyboard, completion actions, packaging, and timeline.
- `RenderTimeline` is the shared contract between frontend timeline preview and render backends.
- `TaskEvent` is the shared contract for long-task progress, SSE, and polling.

Do not bypass these contracts with ad hoc JSON shapes. If a contract must change, update schemas, TypeScript types, tests, and the relevant plan/spec notes together.

## Long Task Progress

```text
SQLite task/artifact state is authoritative.
SSE is the primary realtime channel.
Polling is the fallback and page-refresh recovery channel.
```

```http
GET /api/tasks/{task_id}/events
GET /api/tasks/{task_id}
```

The SSE route supports `?once=true` for tests and one-shot reads. Frontend clients should use default streaming behavior.

## Storage Rules

Runtime artifacts belong under:

```text
storage/projects/{projectId}/
storage/global/cookies/
```

API-local runtime storage is ignored:

```text
services/api/storage/*
```

Do not commit generated videos, SQLite databases, temp files, model outputs, or runtime artifacts. Register artifacts through `ArtifactStore` and persist only references in SQLite.

## Worktree And Branch Workflow

Use isolated worktrees for feature work. Do not implement substantial features directly on `main`.

P0 branches listed above are merged; new work should start from current `main` with a new `feature/<name>` or `integration/<name>` branch.

```powershell
git worktree add .worktrees/<name> -b feature/<name> main
```

Ensure `.worktrees/` remains ignored.

## Post-P0 Development

When extending beyond P0:

1. Read `docs/superpowers/specs/2026-05-27-videomaker-design.md` for boundaries.
2. Use `docs/superpowers/plans/P0/` for how the current system works; add new plans under `docs/superpowers/plans/YYYY-MM-DD-<module-name>-plan.md`.
3. Do not parallelize schema changes casually — update `packages/contracts` first, then dependents.
4. Run module verification (below) before claiming work is done.

Likely post-P0 themes (not yet planned here): real LLM structure extraction, async job queue, production auth, richer editor UX, full MP4 render automation.

## Testing Expectations

Use TDD for implementation work. Write tests first, confirm they fail for the expected reason, then implement the minimum code to pass.

Before claiming a module is done, run the relevant verification commands:

```powershell
cd packages/contracts
npm run check
npm run validate:schemas
```

```powershell
cd services/api
python -m pytest
python -m compileall app
```

```powershell
cd services/worker
python -m pytest
python -m compileall app
```

```powershell
cd apps/web
npm run typecheck
npm run test
```

Document new module-specific commands in the subsystem plan file.

## Code Style And Safety

- Keep module boundaries narrow and contract-driven.
- Prefer small focused files over large mixed-responsibility files.
- Do not commit runtime artifacts or generated media.
- Do not let LLM output execute code.
- Validate model/agent JSON output against schemas before use.
- Do not copy sample video content; migrate structure and creative method only.
- Avoid broad refactors unrelated to the active plan.

## Notes For New AI Sessions

When starting a new session:

1. Read this file first.
2. Read `docs/superpowers/specs/2026-05-27-videomaker-design.md`.
3. For P0 behavior, read the relevant plan in `docs/superpowers/plans/P0/` (or the master P0 plan).
4. For new features, read or write the active plan under `docs/superpowers/plans/`.
5. Check `git status --short`.
6. Use a feature worktree unless the user explicitly asks for a small docs-only change on `main`.
7. Run existing tests before and after changes.
8. Keep commits scoped to the task.

## Plan Quality Gate

Subsystem plans are executable specifications, not lightweight outlines. Before handing a plan to a new AI session, confirm it states:

- Exact user-facing P0 flows owned by the module.
- Exact API routes, request shapes, or artifact shapes the module consumes or produces.
- Concrete algorithms for nontrivial processing, especially video shot detection, keyframe selection, timeline conversion, and slot matching.
- Tool collaboration order and fallback behavior when optional binaries or model services are missing.
- Files allowed to change and files explicitly out of scope.
- Tests that prove both happy path and fallback/error behavior.

Do not hand off a plan that leaves core behavior to "decide during implementation." If a plan is intentionally deferring a capability to integration, it must name the integration plan and the exact route/artifact that will complete it.
