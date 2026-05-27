# Web Workbench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the P0 frontend workbench shell that can display task progress, sample analysis, structure slots, gap reports, timeline previews, and generation results using fixtures first and API endpoints later.

**Architecture:** Implement a Next.js app under `apps/web` using shared TypeScript contracts. The frontend should be contract-driven and able to run with local JSON fixtures before backend/worker integration is complete.

**Tech Stack:** Next.js, React, TypeScript, shared `@videomaker/contracts` types, native `EventSource` for SSE.

---

## Scope And Boundaries

Branch/worktree:

```powershell
git worktree add .worktrees/web-workbench -b feature/web-workbench main
```

Allowed to create/modify:

- `apps/web/**`
- `docs/superpowers/plans/2026-05-27-web-workbench-plan.md`

Do not modify:

- `packages/contracts/**`
- `services/api/**`
- `services/worker/**`

## Task 1: Next.js Shell

**Files:**
- Create: `apps/web/package.json`
- Create: `apps/web/tsconfig.json`
- Create: `apps/web/app/layout.tsx`
- Create: `apps/web/app/projects/page.tsx`
- Create: `apps/web/app/projects/[projectId]/page.tsx`

- [ ] Write a minimal smoke test or type-check target that imports the app route components.
- [ ] Create the Next.js app shell with project list and project detail route.
- [ ] Add a local API base URL config helper.
- [ ] Run `npm install`, `npm run typecheck`, and `npm run build`.
- [ ] Commit: `feat(web): add workbench shell`.

## Task 2: Task Progress Hook

**Files:**
- Create: `apps/web/features/tasks/useTaskProgress.ts`
- Create: `apps/web/features/tasks/TaskProgressPanel.tsx`
- Create: `apps/web/features/tasks/useTaskProgress.test.ts`

- [ ] Write failing tests for SSE-first behavior and polling fallback after repeated SSE failures.
- [ ] Implement `useTaskProgress({apiBaseUrl, taskId})` using `EventSource`.
- [ ] Fall back to `GET /api/tasks/{taskId}` polling every 3 seconds after 3 SSE failures.
- [ ] Render task status, stage, progress, message, artifacts, and error.
- [ ] Run `npm run test` and `npm run typecheck`.
- [ ] Commit: `feat(web): add task progress hook and panel`.

## Task 3: Fixtures And Contract Views

**Files:**
- Create: `apps/web/fixtures/video-structure.fixture.ts`
- Create: `apps/web/fixtures/gap-report.fixture.ts`
- Create: `apps/web/fixtures/generation-plan.fixture.ts`
- Create: `apps/web/features/sample-analysis/SampleAnalysisView.tsx`
- Create: `apps/web/features/structure-mapping/StructureSlotBoard.tsx`
- Create: `apps/web/features/gap-report/GapReportView.tsx`

- [ ] Write type-level fixture checks using shared contract types.
- [ ] Build sample analysis and structure slot visualizations from fixtures.
- [ ] Build gap report cards showing matched, weak, and missing slots.
- [ ] Keep all views usable without backend data.
- [ ] Run `npm run typecheck`.
- [ ] Commit: `feat(web): add structure and gap visualizations`.

## Task 4: Timeline And Result Views

**Files:**
- Create: `apps/web/features/timeline-preview/TimelinePreview.tsx`
- Create: `apps/web/features/generation-result/GenerationResultView.tsx`
- Modify: `apps/web/app/projects/[projectId]/page.tsx`

- [ ] Write tests or story fixtures proving all `TimelineTrackType` values render without crashing.
- [ ] Implement compact timeline tracks with stable clip positions.
- [ ] Implement generation result view for storyboard, timeline, preview link, and video output placeholder.
- [ ] Run `npm run test`, `npm run typecheck`, and `npm run build`.
- [ ] Commit: `feat(web): add timeline and generation result views`.

## Verification

Run before handoff:

```powershell
cd apps/web
npm run test
npm run typecheck
npm run build
```

Also run:

```powershell
cd packages/contracts
npm run check
```

