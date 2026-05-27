# AGENTS.md

## Project Context

VideoMaker is a competition project for an AI short-video creation system. The product goal is a "viral structure migration engine": analyze high-performing sample videos, extract reusable creative structure, map that structure to a new topic or user assets, identify material gaps, and generate an explainable storyboard, timeline, packaging plan, and demo video.

The competition brief is stored in `VideoMaker.md`. The user's original solution sketch is stored in `VideoMakerDesign.md`. The refined project design and implementation plans are the source of truth for development:

- `docs/superpowers/specs/2026-05-27-videomaker-design.md`
- `docs/superpowers/plans/2026-05-27-videomaker-p0-implementation-plan.md`
- `docs/superpowers/plans/2026-05-27-contracts-foundation-plan.md`
- `docs/superpowers/plans/2026-05-27-api-task-artifacts-plan.md`
- `docs/superpowers/plans/2026-05-27-worker-video-analysis-plan.md`
- `docs/superpowers/plans/2026-05-27-web-workbench-plan.md`
- `docs/superpowers/plans/2026-05-27-agent-generation-plan.md`
- `docs/superpowers/plans/2026-05-27-hyperframes-render-plan.md`
- `docs/superpowers/plans/2026-05-27-integration-p0-demo-flow-plan.md`

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

## Current Implementation State

The following foundations are already merged into `main`:

### Contracts Foundation

Package: `packages/contracts`

Includes TypeScript types and JSON Schemas for:

- `ArtifactRef`
- `ToolError`
- `TaskEvent`
- `VideoStructure`
- `AssetInventory`
- `GapReport`
- `GenerationPlan`
- `RenderTimeline`

Validation commands:

```powershell
cd packages/contracts
npm run check
npm run validate:schemas
```

### API Task / Artifact Foundation

Service: `services/api`

Implemented:

- FastAPI app factory: `app.main.create_app`
- SQLite schema/session
- `TaskEventService`
- `ArtifactStore`
- task routes
- SSE progress stream
- polling fallback endpoint
- retry and cancel endpoints

Implemented endpoints:

```http
GET /health
POST /api/tasks
GET /api/tasks/{task_id}
POST /api/tasks/{task_id}/events
GET /api/tasks/{task_id}/events
POST /api/tasks/{task_id}/retry
POST /api/tasks/{task_id}/cancel
```

API validation commands:

```powershell
cd services/api
python -m pytest
python -m compileall app
```

`services/api/pyproject.toml` sets pytest `--basetemp=.pytest-tmp` because the default Windows temp path may be inaccessible in this environment.

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

Use this policy for long-running work:

```text
SQLite task/artifact state is authoritative.
SSE is the primary realtime channel.
Polling is the fallback and page-refresh recovery channel.
```

SSE endpoint:

```http
GET /api/tasks/{task_id}/events
```

Polling endpoint:

```http
GET /api/tasks/{task_id}
```

The current SSE route supports `?once=true` for tests and one-shot reads. Default behavior should be used by frontend clients.

## Storage Rules

Runtime artifacts belong under:

```text
storage/projects/{projectId}/
```

API-local runtime storage is ignored:

```text
services/api/storage/*
```

Do not commit generated videos, SQLite databases, temp files, model outputs, or runtime artifacts. Register artifacts through `ArtifactStore` and persist only references in SQLite.

## Worktree And Branch Workflow

Use isolated worktrees for feature work. Do not implement substantial features directly on `main`.

Current completed branches:

- `feature/contracts-foundation`
- `feature/api-task-artifacts`

Recommended next branches:

- `feature/worker-video-analysis`
- `feature/web-workbench`
- `feature/agent-generation`
- `feature/hyperframes-render`
- `integration/p0-demo-flow`

Recommended pattern:

```powershell
git worktree add .worktrees/<name> -b feature/<name> main
```

Before creating project-local worktrees, ensure `.worktrees/` remains ignored.

## Development Order

Already completed:

1. repository docs and P0 design
2. contracts foundation
3. API task/artifact foundation

Recommended next work:

1. `worker-video-analysis`: FFmpeg/OpenCV/Whisper adapters, sample analysis artifacts, progress events.
2. `web-workbench`: frontend shell, task progress hook, structure/gap/timeline visualization using fixtures and API endpoints.
3. `agent-generation`: structure extraction, asset inventory, slot mapping, gap report, generation plan.
4. `hyperframes-render`: convert `RenderTimeline` to HyperFrames preview/render outputs.
5. `integration/p0-demo-flow`: wire actual end-to-end demo.

Do not parallelize schema changes casually. Contracts must be reviewed and merged before dependent branches consume them.

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

For frontend, worker, agent, and render modules, add module-specific tests and document commands in the relevant plan file before implementation.

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
2. Read the main design spec.
3. Read the relevant plan file for the task.
4. Check `git status --short`.
5. Use a feature worktree unless the user explicitly asks for a small docs-only change on `main`.
6. Run existing tests before and after changes.
7. Keep commits scoped to the task.

If the user asks to start a new module, first create or update a subsystem plan under:

```text
docs/superpowers/plans/YYYY-MM-DD-<module-name>-plan.md
```

Then implement that plan task-by-task with verification and commits.
