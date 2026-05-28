# Web Workbench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the P0 frontend workbench shell that can display task progress, sample analysis, structure slots, gap reports, timeline previews, and generation results using fixtures first and API endpoints later.

**Architecture:** Implement a Next.js app under `apps/web` using shared TypeScript contracts. The frontend should be contract-driven and able to run with local JSON fixtures before backend/worker integration is complete.

**Tech Stack:** Next.js, React, TypeScript, Tailwind CSS, shadcn/ui, shared `@videomaker/contracts` types, native `EventSource` for SSE.

**Design System:** All UI development must follow the [UI/UX Design System Specification](../specs/2026-05-28-ui-ux-design-system.md) using dual-theme Bento/Pro implementations.

---

## Required P0 User Flows

The web workbench must support these P0 inputs, even if early implementation uses fixture data behind the scenes:

- Create/open a project.
- Add a sample video by local upload.
- Add a sample video by URL, which triggers backend/worker `yt-dlp` download.
- Add user assets by uploading images and videos.
- Add a text brief with topic, product name, selling points, audience, required mentions, and forbidden mentions.
- Start sample analysis and show progress through SSE with polling fallback.
- Start generation and show `VideoStructure`, `AssetInventory`, `GapReport`, `GenerationPlan`, and `RenderTimeline` views when available.

The frontend must not run `yt-dlp`, FFmpeg, OpenCV, or model code. It only submits files/URLs/briefs to API routes and renders task progress and artifacts.

## API Contract Expected By Web

The web module should implement an `apiClient` against these expected routes. If a route is not implemented yet, keep a fixture fallback and make the missing route explicit in code comments and tests.

```http
POST /api/projects
GET /api/projects/{projectId}
POST /api/projects/{projectId}/samples/upload
POST /api/projects/{projectId}/samples/from-url
POST /api/projects/{projectId}/assets/upload
POST /api/projects/{projectId}/brief
POST /api/samples/{sampleId}/analyze
GET /api/tasks/{taskId}
GET /api/tasks/{taskId}/events
GET /api/samples/{sampleId}/analysis
GET /api/samples/{sampleId}/structure
POST /api/projects/{projectId}/generation-plan
GET /api/generations/{generationId}
```

Expected request shapes:

```ts
type CreateSampleFromUrlRequest = {
  url: string;
};

type UserBriefRequest = {
  topic?: string;
  productName?: string;
  sellingPoints: string[];
  targetAudience?: string;
  tone?: string;
  mustMention: string[];
  avoidMention: string[];
};
```

Local upload should use `multipart/form-data` field name `file`. URL import should show the same progress UI as local upload/analysis because the backend will create a task for download and analysis.

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

- [x] Write a minimal smoke test or type-check target that imports the app route components.
- [x] Create the Next.js app shell with project list and project detail route.
- [x] Initialize Tailwind CSS and shadcn/ui with CSS variables for dual-theme (Bento/Pro) configuration.
- [x] Add a local API base URL config helper.
- [x] Run `npm install`, `npm run typecheck`, and `npm run build`.
- [ ] Commit: `feat(web): add workbench shell with UI foundation`.

## Task 2: API Client And Input Forms

**Files:**
- Create: `apps/web/lib/apiClient.ts`
- Create: `apps/web/features/project-input/SampleInputPanel.tsx`
- Create: `apps/web/features/project-input/AssetInputPanel.tsx`
- Create: `apps/web/features/project-input/BriefEditor.tsx`
- Create: `apps/web/features/project-input/projectInput.test.tsx`

- [x] Write failing tests for local sample upload request shape, sample URL request shape, asset upload request shape, and brief submission shape.
- [x] Implement `createProject`, `uploadSampleVideo`, `importSampleFromUrl`, `uploadAsset`, `saveBrief`, `startSampleAnalysis`, and `createGenerationPlan` in `apiClient.ts`.
- [x] Implement `SampleInputPanel` with two tabs: local file upload and URL import. The URL tab must call `/samples/from-url`; it must not call `yt-dlp` directly.
- [x] Implement `AssetInputPanel` for image/video asset uploads with accepted MIME types `image/*` and `video/*`.
- [x] Implement `BriefEditor` with structured fields matching `UserBriefRequest`.
- [x] Run `npm run test` and `npm run typecheck`.
- [ ] Commit: `feat(web): add sample asset and brief input flows`.

## Task 3: Task Progress Hook

**Files:**
- Create: `apps/web/features/tasks/useTaskProgress.ts`
- Create: `apps/web/features/tasks/TaskProgressPanel.tsx`
- Create: `apps/web/features/tasks/useTaskProgress.test.ts`

- [x] Write failing tests for SSE-first behavior and polling fallback after repeated SSE failures.
- [x] Implement `useTaskProgress({apiBaseUrl, taskId})` using `EventSource`.
- [x] Fall back to `GET /api/tasks/{taskId}` polling every 3 seconds after 3 SSE failures.
- [x] Render task status, stage, progress, message, artifacts, and error.
- [x] Run `npm run test` and `npm run typecheck`.
- [ ] Commit: `feat(web): add task progress hook and panel`.

## Task 4: Fixtures And Contract Views

**Files:**
- Create: `apps/web/fixtures/video-structure.fixture.ts`
- Create: `apps/web/fixtures/gap-report.fixture.ts`
- Create: `apps/web/fixtures/generation-plan.fixture.ts`
- Create: `apps/web/features/sample-analysis/SampleAnalysisView.tsx`
- Create: `apps/web/features/structure-mapping/StructureSlotBoard.tsx`
- Create: `apps/web/features/gap-report/GapReportView.tsx`

- [x] Write type-level fixture checks using shared contract types.
- [x] Build sample analysis and structure slot visualizations from fixtures.
- [x] Build gap report cards showing matched, weak, and missing slots.
- [x] Keep all views usable without backend data.
- [x] Run `npm run typecheck`.
- [ ] Commit: `feat(web): add structure and gap visualizations`.

## Task 5: Timeline And Result Views

**Files:**
- Create: `apps/web/features/timeline-preview/TimelinePreview.tsx`
- Create: `apps/web/features/generation-result/GenerationResultView.tsx`
- Modify: `apps/web/app/projects/[projectId]/page.tsx`

- [x] Write tests or story fixtures proving all `TimelineTrackType` values render without crashing.
- [x] Implement compact timeline tracks with stable clip positions.
- [x] Implement generation result view for storyboard, timeline, preview link, and video output placeholder.
- [x] Run `npm run test`, `npm run typecheck`, and `npm run build`.
- [ ] Commit: `feat(web): add timeline and generation result views`.

## Task 6: Project Workbench Composition

**Files:**
- Modify: `apps/web/app/projects/[projectId]/page.tsx`
- Create: `apps/web/features/workbench/ProjectWorkbench.tsx`
- Create: `apps/web/features/workbench/ProjectWorkbench.test.tsx`

- [x] Write failing tests that prove the workbench can switch between sample input, analysis progress, structure mapping, gap report, timeline, and result panels.
- [x] Compose `SampleInputPanel`, `AssetInputPanel`, `BriefEditor`, `TaskProgressPanel`, structure views, and timeline/result views into one project workspace.
- [x] Use fixture data when API endpoints are unavailable, but keep API client calls wired behind explicit action handlers.
- [x] Run `npm run test`, `npm run typecheck`, and `npm run build`.
- [ ] Commit: `feat(web): compose p0 project workbench`.

## Acceptance Criteria

- A user can choose a local sample video file and start a sample upload action.
- A user can paste a video URL and start a URL import action that calls `/samples/from-url`.
- A user can upload image/video assets separately from the sample video.
- A user can enter a structured brief.
- The UI can show task progress from SSE and recover through polling.
- The project page can show sample analysis, structure slots, gap report, timeline, and result views from fixtures before real integration.

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

## Architecture Addendum: BFF Proxy

The browser must not call `VIDEOMAKER_API_URL` directly. All API traffic goes through same-origin Next.js Route Handlers:

```text
Browser → /api/* (apps/web/app/api/[...path]) → VIDEOMAKER_API_URL/api/*
```

See [`apps/web/README.md`](../../../apps/web/README.md) and [`2026-05-28-web-workbench-hardening-plan.md`](2026-05-28-web-workbench-hardening-plan.md).
