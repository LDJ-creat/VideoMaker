# VideoMaker P0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the P0 version of VideoMaker: a可解释的爆款视频结构迁移系统，支持样例解析、结构抽取、素材匹配、缺口补全、时间线生成、长任务进度展示和 HyperFrames demo。

**Architecture:** Use a monorepo with Next.js frontend, FastAPI backend, Python worker, shared TypeScript / JSON Schema contracts, SQLite metadata storage, and local filesystem artifacts. Long tasks write authoritative status to the database, stream progress through SSE, and fall back to polling.

**Tech Stack:** Next.js, TypeScript, FastAPI, Python, SQLite, FFmpeg, OpenCV, fast-whisper, HyperFrames, JSON Schema, SSE, local artifact storage.

---

## 1. Execution Strategy

The work must start with shared contracts and skeleton infrastructure. After contracts land, development can split into independent worktrees for frontend, backend API, worker/video analysis, Agent/generation, and rendering.

Recommended branch names:

```text
main
feature/contracts-foundation
feature/api-task-artifacts
feature/web-workbench
feature/worker-video-analysis
feature/agent-generation
feature/hyperframes-render
```

Use worktrees only after `feature/contracts-foundation` is merged into `main`, because all parallel branches depend on the same contracts and project layout.

## 2. File Structure To Create

```text
apps/web/                         Next.js frontend
services/api/                     FastAPI API service
services/worker/                  Python long-task worker
packages/contracts/               Shared schemas and TS types
packages/prompts/                 Agent prompts
storage/.gitkeep                  Local artifact root placeholder
docs/superpowers/plans/           Implementation plans
```

Key files:

```text
packages/contracts/schemas/artifact-ref.schema.json
packages/contracts/schemas/task-event.schema.json
packages/contracts/schemas/video-structure.schema.json
packages/contracts/schemas/asset-inventory.schema.json
packages/contracts/schemas/gap-report.schema.json
packages/contracts/schemas/generation-plan.schema.json
packages/contracts/schemas/render-timeline.schema.json
packages/contracts/src/types.ts

services/api/app/main.py
services/api/app/db/schema.sql
services/api/app/db/session.py
services/api/app/routers/tasks.py
services/api/app/routers/projects.py
services/api/app/routers/samples.py
services/api/app/routers/assets.py
services/api/app/routers/generations.py
services/api/app/services/artifact_store.py
services/api/app/services/task_events.py

services/worker/app/runtime/task_context.py
services/worker/app/runtime/artifact_store.py
services/worker/app/tools/ffmpeg_tool.py
services/worker/app/tools/whisper_tool.py
services/worker/app/tools/opencv_tool.py
services/worker/app/tools/llm_tool.py
services/worker/app/pipelines/sample_pipeline.py
services/worker/app/pipelines/generation_pipeline.py

apps/web/app/projects/page.tsx
apps/web/app/projects/[projectId]/page.tsx
apps/web/features/tasks/useTaskProgress.ts
apps/web/features/sample-analysis/
apps/web/features/structure-mapping/
apps/web/features/gap-report/
apps/web/features/timeline-preview/
apps/web/features/generation-result/
```

## 3. Development Order Guide

### 3.1 Must Be Sequential

These tasks cannot be parallelized safely:

1. **Contracts foundation** must land first. Every other module consumes `TaskEvent`, `ArtifactRef`, `VideoStructure`, `AssetInventory`, `GapReport`, `GenerationPlan`, and `RenderTimeline`.
2. **Project skeleton** must land before worktrees split. The repo layout, package managers, lint commands, and test commands must be shared.
3. **Task/artifact backend** must land before full worker and frontend progress integration. Workers and UI need stable task APIs.
4. **Sample analysis output contract** must land before structure Agent and frontend sample visualization finalize.
5. **RenderTimeline contract** must land before HyperFrames renderer and timeline UI finalize.

### 3.2 Can Be Parallel After Contracts

After Task 1 and Task 2 are merged, these streams can run in separate worktrees:

| Stream | Branch | Depends On | Can Run With |
| --- | --- | --- | --- |
| Backend task/artifact API | `feature/api-task-artifacts` | contracts | frontend shell, worker tools |
| Frontend workbench | `feature/web-workbench` | contracts, mocked API | backend, worker, renderer |
| Video analysis worker | `feature/worker-video-analysis` | contracts, artifact store interface | frontend, Agent |
| Agent/generation pipeline | `feature/agent-generation` | contracts, sample analysis fixtures | frontend, renderer |
| HyperFrames renderer | `feature/hyperframes-render` | RenderTimeline schema | frontend, Agent |

### 3.3 Integration Order

Merge order should be:

```text
1. feature/contracts-foundation
2. feature/api-task-artifacts
3. feature/worker-video-analysis
4. feature/agent-generation
5. feature/hyperframes-render
6. feature/web-workbench
7. integration/p0-demo-flow
```

The frontend branch can be developed early with mock JSON fixtures, but should merge after backend and worker APIs stabilize to reduce churn.

## 4. Worktree Setup Guide

Before executing a parallel stream, run worktree detection from the current repository:

```powershell
git rev-parse --show-toplevel
git rev-parse --git-dir
git rev-parse --git-common-dir
git branch --show-current
```

If no isolated workspace exists and `.worktrees` is ignored, create a worktree:

```powershell
git worktree add .worktrees/api-task-artifacts -b feature/api-task-artifacts main
git worktree add .worktrees/web-workbench -b feature/web-workbench main
git worktree add .worktrees/worker-video-analysis -b feature/worker-video-analysis main
git worktree add .worktrees/agent-generation -b feature/agent-generation main
git worktree add .worktrees/hyperframes-render -b feature/hyperframes-render main
```

Before creating project-local worktrees, `.worktrees/` must be in `.gitignore`.

## 5. Task Plan

### Task 1: Repository Foundation And Ignore Rules

**Files:**
- Create: `.gitignore`
- Create: `storage/.gitkeep`
- Create: `docs/architecture/.gitkeep`

- [ ] **Step 1: Add repository ignore rules**

Create `.gitignore`:

```gitignore
# Dependencies
node_modules/
.venv/
__pycache__/
.pytest_cache/

# Build outputs
.next/
dist/
build/
*.egg-info/

# Local runtime artifacts
storage/*
!storage/.gitkeep

# Local env
.env
.env.local

# Worktrees
.worktrees/

# OS/editor
.DS_Store
Thumbs.db
.idea/
.vscode/
```

- [ ] **Step 2: Add placeholder directories**

Create:

```text
storage/.gitkeep
docs/architecture/.gitkeep
```

- [ ] **Step 3: Verify git sees only intended files**

Run:

```powershell
git status --short
```

Expected: `.gitignore`, `storage/.gitkeep`, and `docs/architecture/.gitkeep` appear as new files.

- [ ] **Step 4: Commit**

```powershell
git add .gitignore storage/.gitkeep docs/architecture/.gitkeep
git commit -m "chore: initialize repository foundation"
```

### Task 2: Shared Contracts Foundation

**Files:**
- Create: `packages/contracts/package.json`
- Create: `packages/contracts/schemas/artifact-ref.schema.json`
- Create: `packages/contracts/schemas/task-event.schema.json`
- Create: `packages/contracts/schemas/video-structure.schema.json`
- Create: `packages/contracts/schemas/asset-inventory.schema.json`
- Create: `packages/contracts/schemas/gap-report.schema.json`
- Create: `packages/contracts/schemas/generation-plan.schema.json`
- Create: `packages/contracts/schemas/render-timeline.schema.json`
- Create: `packages/contracts/src/types.ts`

- [ ] **Step 1: Create contracts package manifest**

Create `packages/contracts/package.json`:

```json
{
  "name": "@videomaker/contracts",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "main": "src/types.ts",
  "scripts": {
    "check": "tsc --noEmit"
  },
  "devDependencies": {
    "typescript": "^5.4.0"
  }
}
```

- [ ] **Step 2: Create ArtifactRef schema**

Create `packages/contracts/schemas/artifact-ref.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://videomaker.local/schemas/artifact-ref.schema.json",
  "title": "ArtifactRef",
  "type": "object",
  "required": ["id", "type", "uri", "createdAt"],
  "properties": {
    "id": { "type": "string" },
    "type": {
      "type": "string",
      "enum": ["video", "audio", "image", "json", "text", "html", "render"]
    },
    "uri": { "type": "string" },
    "createdAt": { "type": "string", "format": "date-time" }
  },
  "additionalProperties": false
}
```

- [ ] **Step 3: Create TaskEvent schema**

Create `packages/contracts/schemas/task-event.schema.json` with the `TaskEvent` fields from the design document: `taskId`, `status`, `stage`, `progress`, `message`, `artifactRefs`, `error`, `updatedAt`.

- [ ] **Step 4: Create core domain schemas**

Create the remaining schema files using the fields from the design document. Keep the P0 schemas strict enough to validate required IDs, roles, time ranges, and source references, but allow optional metadata objects where model output may vary.

- [ ] **Step 5: Create TypeScript type exports**

Create `packages/contracts/src/types.ts`:

```ts
export type TaskStatus =
  | "queued"
  | "running"
  | "succeeded"
  | "failed"
  | "cancelled"
  | "retrying";

export type ArtifactType =
  | "video"
  | "audio"
  | "image"
  | "json"
  | "text"
  | "html"
  | "render";

export type ArtifactRef = {
  id: string;
  type: ArtifactType;
  uri: string;
  createdAt: string;
};

export type TaskEvent = {
  taskId: string;
  status: TaskStatus;
  stage:
    | "uploading"
    | "extracting_metadata"
    | "extracting_audio"
    | "transcribing"
    | "detecting_shots"
    | "extracting_keyframes"
    | "extracting_structure"
    | "analyzing_assets"
    | "mapping_slots"
    | "planning_completion"
    | "generating_storyboard"
    | "building_timeline"
    | "rendering"
    | "completed";
  progress: number;
  message: string;
  artifactRefs?: ArtifactRef[];
  error?: {
    code: string;
    message: string;
    retryable: boolean;
    details?: unknown;
  };
  updatedAt: string;
};

export type StructureSlotRole =
  | "hook_visual"
  | "hook_text"
  | "product_closeup"
  | "usage_scene"
  | "benefit_card"
  | "comparison"
  | "proof"
  | "transition"
  | "cta";

export type TimelineTrackType =
  | "video"
  | "image"
  | "text"
  | "voiceover"
  | "bgm"
  | "effect"
  | "transition";
```

- [ ] **Step 6: Verify contracts package**

Run:

```powershell
cd packages/contracts
npm install
npm run check
```

Expected: TypeScript check passes.

- [ ] **Step 7: Commit**

```powershell
git add packages/contracts
git commit -m "feat: add shared p0 contracts"
```

### Task 3: Backend API Skeleton With Task And Artifact State

**Files:**
- Create: `services/api/pyproject.toml`
- Create: `services/api/app/main.py`
- Create: `services/api/app/db/schema.sql`
- Create: `services/api/app/db/session.py`
- Create: `services/api/app/services/artifact_store.py`
- Create: `services/api/app/services/task_events.py`
- Create: `services/api/app/routers/tasks.py`

- [ ] **Step 1: Create FastAPI package**

Create `services/api/pyproject.toml`:

```toml
[project]
name = "videomaker-api"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "fastapi>=0.111",
  "uvicorn[standard]>=0.30",
  "pydantic>=2.7"
]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Create database schema**

Create `services/api/app/db/schema.sql` with tables:

```sql
CREATE TABLE IF NOT EXISTS tasks (
  id TEXT PRIMARY KEY,
  project_id TEXT,
  status TEXT NOT NULL,
  stage TEXT NOT NULL,
  progress INTEGER NOT NULL,
  message TEXT NOT NULL,
  error_json TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS artifacts (
  id TEXT PRIMARY KEY,
  project_id TEXT,
  task_id TEXT,
  type TEXT NOT NULL,
  uri TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS task_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id TEXT NOT NULL,
  event_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);
```

- [ ] **Step 3: Implement task event service**

Implement `services/api/app/services/task_events.py` with functions to create tasks, update status, append events, fetch current task, and stream recent events by task id.

- [ ] **Step 4: Implement SSE route**

Create `GET /api/tasks/{task_id}/events` in `routers/tasks.py`. It should emit `event: task` and `data: <json>` lines, then keep the connection open while the task is not terminal.

- [ ] **Step 5: Implement polling route**

Create `GET /api/tasks/{task_id}` returning the latest task row and associated artifact refs.

- [ ] **Step 6: Verify API starts**

Run:

```powershell
cd services/api
python -m uvicorn app.main:app --reload
```

Expected: API starts and `/docs` loads locally.

- [ ] **Step 7: Commit**

```powershell
git add services/api
git commit -m "feat(api): add task progress and artifact foundation"
```

### Task 4: Frontend Workbench Shell And Task Progress Hook

**Files:**
- Create: `apps/web/package.json`
- Create: `apps/web/app/layout.tsx`
- Create: `apps/web/app/projects/page.tsx`
- Create: `apps/web/app/projects/[projectId]/page.tsx`
- Create: `apps/web/features/tasks/useTaskProgress.ts`
- Create: `apps/web/features/tasks/TaskProgressPanel.tsx`

- [ ] **Step 1: Create Next.js app shell**

Initialize the app under `apps/web` and add scripts:

```json
{
  "name": "videomaker-web",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "lint": "next lint"
  },
  "dependencies": {
    "next": "^15.0.0",
    "react": "^19.0.0",
    "react-dom": "^19.0.0"
  },
  "devDependencies": {
    "typescript": "^5.4.0",
    "@types/node": "^20.0.0",
    "@types/react": "^19.0.0"
  }
}
```

- [ ] **Step 2: Implement task progress hook**

Create `useTaskProgress.ts`:

```ts
import { useEffect, useState } from "react";
import type { TaskEvent } from "@videomaker/contracts/src/types";

type Options = {
  apiBaseUrl: string;
  taskId?: string;
};

export function useTaskProgress({ apiBaseUrl, taskId }: Options) {
  const [event, setEvent] = useState<TaskEvent | null>(null);
  const [mode, setMode] = useState<"idle" | "sse" | "polling">("idle");

  useEffect(() => {
    if (!taskId) return;

    let closed = false;
    let retryCount = 0;
    let pollTimer: ReturnType<typeof setInterval> | undefined;

    const startPolling = () => {
      setMode("polling");
      pollTimer = setInterval(async () => {
        const response = await fetch(`${apiBaseUrl}/api/tasks/${taskId}`);
        if (!response.ok) return;
        const next = (await response.json()) as TaskEvent;
        setEvent(next);
        if (["succeeded", "failed", "cancelled"].includes(next.status)) {
          if (pollTimer) clearInterval(pollTimer);
        }
      }, 3000);
    };

    const connect = () => {
      setMode("sse");
      const source = new EventSource(`${apiBaseUrl}/api/tasks/${taskId}/events`);

      source.addEventListener("task", (message) => {
        setEvent(JSON.parse((message as MessageEvent).data));
      });

      source.onerror = () => {
        source.close();
        retryCount += 1;
        if (closed) return;
        if (retryCount <= 3) {
          window.setTimeout(connect, 1000 * retryCount);
        } else {
          startPolling();
        }
      };
    };

    connect();

    return () => {
      closed = true;
      if (pollTimer) clearInterval(pollTimer);
    };
  }, [apiBaseUrl, taskId]);

  return { event, mode };
}
```

- [ ] **Step 3: Implement progress panel**

Create a panel that displays status, stage, progress bar, message, artifact count, and error message.

- [ ] **Step 4: Verify frontend starts**

Run:

```powershell
cd apps/web
npm install
npm run dev
```

Expected: the project page loads and can render a mocked task event.

- [ ] **Step 5: Commit**

```powershell
git add apps/web
git commit -m "feat(web): add workbench shell and task progress UI"
```

### Task 5: Worker Runtime And Artifact Store

**Files:**
- Create: `services/worker/pyproject.toml`
- Create: `services/worker/app/runtime/task_context.py`
- Create: `services/worker/app/runtime/artifact_store.py`
- Create: `services/worker/app/runtime/task_progress.py`

- [ ] **Step 1: Create worker package**

Create `services/worker/pyproject.toml` with dependencies:

```toml
[project]
name = "videomaker-worker"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "pydantic>=2.7",
  "opencv-python>=4.9",
  "ffmpeg-python>=0.2"
]
```

- [ ] **Step 2: Implement TaskContext**

`TaskContext` must include `project_id`, `task_id`, `storage_root`, `emit_event`, and `register_artifact`.

- [ ] **Step 3: Implement artifact path policy**

Artifacts must be written only under:

```text
storage/projects/{projectId}/
```

Reject paths that resolve outside this root.

- [ ] **Step 4: Commit**

```powershell
git add services/worker
git commit -m "feat(worker): add runtime and artifact store"
```

### Task 6: Sample Video Analysis Pipeline

**Files:**
- Create: `services/worker/app/tools/ffmpeg_tool.py`
- Create: `services/worker/app/tools/opencv_tool.py`
- Create: `services/worker/app/tools/whisper_tool.py`
- Create: `services/worker/app/pipelines/sample_pipeline.py`

- [ ] **Step 1: Implement metadata extraction**

Use FFmpeg to extract duration, resolution, fps, codec, and audio presence into `metadata.json`.

- [ ] **Step 2: Implement audio extraction**

Export audio to `audio.wav` and register it as an artifact.

- [ ] **Step 3: Implement ASR adapter**

Implement `WhisperTool.transcribe(audio_path)` returning transcript segments. If fast-whisper is not installed in local dev, return a clear retryable tool error instead of crashing.

- [ ] **Step 4: Implement shot detection**

Use OpenCV histogram difference or scene thresholding to produce `shots.json`.

- [ ] **Step 5: Implement keyframe extraction**

Export one keyframe per detected shot to `keyframes/`.

- [ ] **Step 6: Emit progress events**

Emit stages:

```text
extracting_metadata
extracting_audio
transcribing
detecting_shots
extracting_keyframes
```

- [ ] **Step 7: Commit**

```powershell
git add services/worker/app/tools services/worker/app/pipelines/sample_pipeline.py
git commit -m "feat(worker): add sample video analysis pipeline"
```

### Task 7: Structure Extraction Agent

**Files:**
- Create: `packages/prompts/agents/structure_analyst.md`
- Create: `services/worker/app/tools/llm_tool.py`
- Create: `services/worker/app/pipelines/structure_pipeline.py`

- [ ] **Step 1: Create prompt**

The prompt must instruct the model to migrate structure only, not copy sample content. It must output `VideoStructure` JSON.

- [ ] **Step 2: Implement LLMTool**

Wrap model calls behind one interface. In local mode, allow fixture output for tests and demos without API keys.

- [ ] **Step 3: Generate VideoStructure**

Combine transcript, shots, keyframes, and metadata into a `VideoStructure` artifact.

- [ ] **Step 4: Validate schema**

Reject invalid structure JSON and save both raw output and validation error.

- [ ] **Step 5: Commit**

```powershell
git add packages/prompts services/worker/app/tools/llm_tool.py services/worker/app/pipelines/structure_pipeline.py
git commit -m "feat(agent): extract video structure from sample analysis"
```

### Task 8: Asset Inventory, Slot Mapping, And Gap Report

**Files:**
- Create: `packages/prompts/agents/slot_mapper.md`
- Create: `packages/prompts/agents/gap_planner.md`
- Create: `services/worker/app/pipelines/generation_pipeline.py`

- [ ] **Step 1: Build AssetInventory from user brief**

Convert topic, product name, selling points, target audience, and uploaded asset metadata into `AssetInventory`.

- [ ] **Step 2: Match slots**

Match `StructureSlot` entries to candidate user assets by required type, semantic intent, duration fit, and importance.

- [ ] **Step 3: Produce GapReport**

For missing or weak slots, output reason, impact, and suggested fixes.

- [ ] **Step 4: Commit**

```powershell
git add packages/prompts/agents/slot_mapper.md packages/prompts/agents/gap_planner.md services/worker/app/pipelines/generation_pipeline.py
git commit -m "feat(agent): add slot mapping and gap report"
```

### Task 9: Generation Plan And RenderTimeline

**Files:**
- Create: `packages/prompts/agents/storyboard_writer.md`
- Create: `packages/prompts/agents/packaging_designer.md`
- Modify: `services/worker/app/pipelines/generation_pipeline.py`

- [ ] **Step 1: Generate storyboard**

Generate `StoryboardScene[]` from `VideoStructure`, `AssetInventory`, and `GapReport`.

- [ ] **Step 2: Generate completion actions**

Support P0 strategies:

```text
text_completion
packaging_completion
asset_reuse
```

- [ ] **Step 3: Generate RenderTimeline**

Create tracks for image/video, text, voiceover placeholder, effects, and transitions.

- [ ] **Step 4: Commit**

```powershell
git add packages/prompts/agents/storyboard_writer.md packages/prompts/agents/packaging_designer.md services/worker/app/pipelines/generation_pipeline.py
git commit -m "feat(agent): generate storyboard and render timeline"
```

### Task 10: HyperFrames Render Backend

**Files:**
- Create: `services/worker/app/tools/hyperframes_tool.py`
- Create: `services/worker/app/render/render_timeline_to_hyperframes.py`

- [ ] **Step 1: Convert RenderTimeline to composition**

Generate a HyperFrames composition directory with `index.html` and local asset references.

- [ ] **Step 2: Render preview**

Generate `preview.html` even if full MP4 render is not available in local dev.

- [ ] **Step 3: Render MP4**

Invoke HyperFrames CLI when available. If unavailable, return a retryable tool error and keep `preview.html`.

- [ ] **Step 4: Emit rendering progress**

Emit `building_timeline`, `rendering`, and `completed` task events.

- [ ] **Step 5: Commit**

```powershell
git add services/worker/app/tools/hyperframes_tool.py services/worker/app/render
git commit -m "feat(render): add hyperframes render backend"
```

### Task 11: Frontend Visualization Features

**Files:**
- Create: `apps/web/features/sample-analysis/SampleAnalysisView.tsx`
- Create: `apps/web/features/structure-mapping/StructureSlotBoard.tsx`
- Create: `apps/web/features/gap-report/GapReportView.tsx`
- Create: `apps/web/features/timeline-preview/TimelinePreview.tsx`
- Create: `apps/web/features/generation-result/GenerationResultView.tsx`

- [ ] **Step 1: Build sample analysis view**

Show video metadata, transcript summary, keyframes, shot count, and package tags.

- [ ] **Step 2: Build structure slot board**

Show slot role, time range, visual intent, script intent, importance, and match status.

- [ ] **Step 3: Build gap report view**

Show missing slots, impact, reason, and selected completion strategy.

- [ ] **Step 4: Build timeline preview**

Render timeline tracks for video/image/text/effect/transition clips.

- [ ] **Step 5: Build result view**

Show storyboard, timeline, preview link, and rendered video if available.

- [ ] **Step 6: Commit**

```powershell
git add apps/web/features apps/web/app/projects
git commit -m "feat(web): visualize structure migration workflow"
```

### Task 12: P0 Integration Flow

**Files:**
- Modify: `services/api/app/routers/projects.py`
- Modify: `services/api/app/routers/samples.py`
- Modify: `services/api/app/routers/assets.py`
- Modify: `services/api/app/routers/generations.py`
- Modify: `apps/web/app/projects/[projectId]/page.tsx`

- [ ] **Step 1: Wire project creation**

Frontend can create or open a project and upload a sample.

- [ ] **Step 2: Wire sample analysis task**

Starting analysis creates a task, worker emits progress, frontend displays SSE progress.

- [ ] **Step 3: Wire generation task**

User brief and assets produce AssetInventory, GapReport, GenerationPlan, RenderTimeline, and render output.

- [ ] **Step 4: Verify refresh recovery**

Start a long task, refresh the browser, and confirm the UI resumes from `GET /api/tasks/{taskId}`.

- [ ] **Step 5: Verify polling fallback**

Disable SSE in the frontend by forcing `EventSource` failure and confirm polling continues progress updates.

- [ ] **Step 6: Commit**

```powershell
git add apps services
git commit -m "feat: integrate p0 structure migration flow"
```

## 6. Test And Verification Matrix

Run before claiming P0 complete:

```powershell
cd packages/contracts
npm run check

cd ../../apps/web
npm run build

cd ../../services/api
python -m pytest

cd ../worker
python -m pytest
```

Manual demo checklist:

1. Create a project.
2. Upload a sample video.
3. See progress through SSE.
4. Refresh during a task and recover status.
5. See sample metadata, transcript, shots, and keyframes.
6. Generate VideoStructure and slot board.
7. Input new brief and limited素材.
8. See GapReport with missing slots and completion actions.
9. Generate storyboard and timeline.
10. Render HyperFrames preview or MP4.
11. Generate a second version without overwriting the first.

## 7. Parallel Development Rules

Do not parallelize:

1. Shared contract changes without first merging to `main`.
2. Backend route names and frontend integration changes unless the API contract is frozen.
3. RenderTimeline schema changes while renderer and timeline UI branches are both active.
4. TaskEvent schema changes while SSE and worker branches are both active.

Safe to parallelize:

1. Frontend UI using JSON fixtures after contracts land.
2. Worker video analysis using local fixture videos.
3. Agent prompts and schema validation using saved analysis fixtures.
4. HyperFrames renderer using RenderTimeline fixtures.
5. API task/artifact routes using synthetic task events.

## 8. Self-Review

Spec coverage:

1. Long-task progress is covered by Tasks 3, 4, 5, 6, 10, and 12.
2. Contracts are covered by Task 2.
3. Sample analysis is covered by Task 6.
4. Structure extraction is covered by Task 7.
5. Asset inventory, slot mapping, and gap handling are covered by Task 8.
6. Storyboard, timeline, and packaging are covered by Task 9.
7. HyperFrames rendering is covered by Task 10.
8. Frontend explainability and visualization are covered by Task 11.
9. P0 integration and fallback behavior are covered by Task 12.

No placeholder tasks are intentionally left. P1 items such as LangfuseSink, AIGC generation, complete timeline editing, and natural-language editing are not part of this P0 execution plan, but the contracts and extension points leave room for them.
