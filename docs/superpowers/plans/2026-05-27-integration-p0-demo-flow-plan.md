# P0 Demo Flow Integration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the completed P0 modules into one demonstrable flow from sample upload/analysis through structure migration, gap report, render timeline, and preview output.

**Architecture:** This plan must run after worker, web, agent, and render feature branches are reviewed and merged. It should not introduce new core abstractions; it should connect existing modules, fix integration seams, and produce a stable demo case.

**Tech Stack:** Existing Next.js frontend, FastAPI API, Python worker, shared contracts, HyperFrames preview backend.

---

## Prerequisites

Do not start this plan until these branches are merged into `main`:

- `feature/worker-video-analysis`
- `feature/web-workbench`
- `feature/agent-generation`
- `feature/hyperframes-render`

Branch/worktree:

```powershell
git worktree add .worktrees/p0-demo-flow -b integration/p0-demo-flow main
```

## Task 1: API Integration Endpoints

**Files:**
- Modify: `services/api/app/routers/samples.py`
- Modify: `services/api/app/routers/assets.py`
- Modify: `services/api/app/routers/generations.py`
- Modify: `services/api/app/main.py`
- Create: `services/api/tests/test_p0_flow_routes.py`

- [ ] Write failing API tests for starting sample analysis and generation tasks.
- [ ] Add routes that create tasks and enqueue/trigger worker pipeline calls in local mode.
- [ ] Return task IDs immediately for long-running operations.
- [ ] Run `python -m pytest`.
- [ ] Commit: `feat(integration): add p0 flow api routes`.

## Task 2: Worker Pipeline Orchestration

**Files:**
- Create: `services/worker/app/pipelines/p0_demo_pipeline.py`
- Create: `services/worker/tests/test_p0_demo_pipeline.py`

- [ ] Write failing tests for orchestrating sample analysis, structure extraction, slot mapping, generation plan, and render preview using fixtures.
- [ ] Implement local synchronous orchestration first; async queue can be added later.
- [ ] Ensure each stage persists artifacts and emits `TaskEvent`.
- [ ] Run `python -m pytest`.
- [ ] Commit: `feat(integration): orchestrate p0 demo pipeline`.

## Task 3: Frontend Real API Wiring

**Files:**
- Modify: `apps/web/app/projects/[projectId]/page.tsx`
- Modify: `apps/web/features/tasks/useTaskProgress.ts`
- Create: `apps/web/lib/apiClient.ts`

- [ ] Write tests or fixture checks for API client request/response shapes.
- [ ] Replace fixture-only data path with API calls where endpoints exist.
- [ ] Keep fixture fallback available for local UI development.
- [ ] Verify page refresh resumes task state through polling endpoint.
- [ ] Run frontend verification commands.
- [ ] Commit: `feat(integration): wire workbench to p0 api`.

## Task 4: Demo Case And Handoff Docs

**Files:**
- Create: `docs/demos/p0-demo-case.md`
- Create: `docs/demos/p0-demo-checklist.md`

- [ ] Document the sample video input assumptions and expected outputs.
- [ ] Document how to start API, worker/local pipeline, and frontend.
- [ ] Document manual demo checklist: upload/sample fixture, progress stream, structure view, gap report, timeline, preview.
- [ ] Commit: `docs: add p0 demo case checklist`.

## Verification

Run all available checks before claiming P0 integration complete:

```powershell
cd packages/contracts
npm run check
npm run validate:schemas

cd ../../services/api
python -m pytest
python -m compileall app

cd ../worker
python -m pytest
python -m compileall app

cd ../../apps/web
npm run test
npm run typecheck
npm run build
```

Manual verification:

1. Start API.
2. Start frontend.
3. Create/open a project.
4. Start sample analysis and observe SSE progress.
5. See sample artifacts and `VideoStructure`.
6. Enter new brief/assets.
7. Generate `GapReport` and `GenerationPlan`.
8. Generate HyperFrames preview.
9. Refresh the browser during a task and confirm status recovery.

