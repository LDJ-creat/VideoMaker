# P1 Web Workbench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade Next.js workbench for P1: structure evidence, variant picker/tabs/compare, **ModelGateway diagnostics**, **P1 task progress + live artifact preview**, AIGC/HyperFrames result badges, NL revise, optional Agent runs drawer, and P1-specific error messages.

**Architecture:** Feature modules under `apps/web/features/`. Consume API via `apiClient`; types from `@videomaker/contracts`. **Phase A** can ship with fixtures after contracts merge. **Phase B** requires multi-variant API, observability `model-gateway` status API, and material completion emitting `artifactRefs` on TaskEvent.

**Tech Stack:** Next.js, TypeScript, React, `useTaskProgress` (extended for multi-task), Tailwind.

**Security note:** API keys stay server-side (env). Frontend only shows **configured / missing** status — no key input in P1 (same boundary as global cookies upload pattern).

---

## Session Context

**Depends on:**

| Phase | Backend dependency |
| --- | --- |
| Phase A (fixtures) | `feature/p1-contracts-extension` |
| Phase B — multi-task | `feature/p1-multi-variant-generation` (see Frontend contract in that plan) |
| Phase B — gateway status | `feature/p1-observability` (`GET /api/settings/model-gateway`) |
| Phase B — live artifacts | AIGC + HyperFrames material merged (worker emits `artifactRefs`) |
| Phase B — NL revise | `feature/p1-nl-revise` |
| Phase B — agent runs | `feature/p1-observability` (`GET /api/generations/{id}/agent-runs`) |

**Master plan:** §10.3, §11, §15 Task 10.

**Branch:** `feature/p1-web-workbench` (single long-lived branch; Phase A early in Wave 1, Phase B after Wave 4–5 backend merges).

---

## Files Allowed To Change

**Create:**

```text
apps/web/features/structure-evidence/StructureEvidencePanel.tsx
apps/web/features/structure-evidence/EvidenceCard.tsx
apps/web/features/generation-variants/VariantTabs.tsx
apps/web/features/generation-variants/VariantCompareView.tsx
apps/web/features/generation-variants/VariantPicker.tsx
apps/web/features/aigc-preview/GeneratedAssetBadge.tsx
apps/web/features/aigc-preview/MaterialPreview.tsx
apps/web/features/nl-revise/ReviseInputBar.tsx
apps/web/features/nl-revise/EditIntentList.tsx
apps/web/features/nl-revise/TimelineDiffSummary.tsx
apps/web/features/settings/ModelGatewayStatusPanel.tsx
apps/web/features/tasks/stageLabels.ts
apps/web/features/tasks/TaskArtifactPreview.tsx
apps/web/features/tasks/MultiTaskProgressPanel.tsx
apps/web/features/tasks/useMultiTaskProgress.ts
apps/web/features/observability/AgentRunsDrawer.tsx
apps/web/lib/formatTaskError.p1.ts          # or extend formatTaskError.ts
apps/web/fixtures/generations/multi-variant.fixture.ts
apps/web/fixtures/edit-intent.fixture.ts
apps/web/fixtures/model-gateway-status.fixture.ts
apps/web/tests/variant-tabs.test.tsx
apps/web/tests/revise-input.test.tsx
apps/web/tests/stage-labels.test.ts
apps/web/tests/task-artifact-preview.test.tsx
apps/web/tests/multi-task-progress.test.tsx
apps/web/tests/model-gateway-status.test.tsx
```

**Modify:**

```text
apps/web/app/projects/[projectId]/page.tsx
apps/web/features/workbench/ProjectWorkbench.tsx
apps/web/features/workbench/ProjectWorkbench.test.tsx
apps/web/features/tasks/TaskProgressPanel.tsx
apps/web/features/tasks/useTaskProgress.ts
apps/web/features/tasks/useTaskProgress.test.ts
apps/web/lib/apiClient.ts
apps/web/lib/server/fixture-resolver.ts
apps/web/features/generation-result/
apps/web/features/gap-report/
apps/web/lib/formatTaskError.ts
```

**Out of scope:** `services/worker/**`, `services/api/**` (except reading types). Do not implement browser-side API key storage.

---

## API Client Extensions

```typescript
export type MultiVariantGenerationResponse = {
  generations: Array<{
    generationId: string;
    variant: string;
    taskId: string;
  }>;
};

export type ModelGatewayStatusResponse = {
  fixtureMode: boolean;
  providers: {
    text: ProviderStatus;
    vision: ProviderStatus;
    tts: ProviderStatus;
    image: ProviderStatus;
    video: ProviderStatus;
  };
};

type ProviderStatus = {
  configured: boolean;
  model?: string;
  driver?: string;
};

export async function createGenerationPlan(
  projectId: string,
  body?: { variants?: string[] }
): Promise<MultiVariantGenerationResponse>;

export async function getModelGatewayStatus(): Promise<ModelGatewayStatusResponse>;

export async function getGenerationAgentRuns(
  generationId: string
): Promise<{ runs: AgentRunLog[] }>;

export async function reviseGeneration(
  generationId: string,
  instruction: string
): Promise<ReviseGenerationResponse>;

export function loadVariantRegistry(): VariantDefinition[];
```

Update `fixture-resolver.ts` for: `POST .../generation-plan` (multi response), `GET settings/model-gateway`, `POST .../revise`, `GET .../agent-runs`.

---

## Phase A — Core P1 UI (fixture-first, Wave 1+)

### UI Requirements

#### 1. Structure Evidence Panel

- Per narrative segment: keyframe thumbnail, transcript excerpt, shot time range.
- Click evidence → highlight slot cards.
- Sample analysis path: when stage is `extracting_structure` or `running_agent`, show message「AI 正在分析样例结构…」.

#### 2. Variant Picker + Tabs

- **VariantPicker** before generate: checkboxes from registry (default: all enabled → `high_click` + `high_conversion`).
- **VariantTabs** after complete: one tab per `generationId` with registry label.
- **VariantCompareView**: side-by-side storyboard count, timeline duration, packaging summary.

#### 3. AIGC / HyperFrames result badges (static)

On gap report and timeline clips (post-complete):

- Provider badge: `image_generation`, `video_generation`, `tts`, `hyperframes_material`.
- `generatedBy` tooltip (model / template).

#### 4. NL Revise

- ReviseInputBar on result panel; EditIntentList during task; TimelineDiffSummary after complete.

---

## Phase B — Progress, diagnostics, live artifacts (Wave 5+)

### 5. Stage labels (`stageLabels.ts`)

Central map for **all** P1 `TaskStage` values. Use in `TaskProgressPanel` and `MultiTaskProgressPanel` — **do not show raw enum** in user-facing UI (keep raw enum in dev-only footer if needed).

```typescript
export const TASK_STAGE_LABELS: Record<TaskStage, string> = {
  // P0 stages — add Chinese if missing
  uploading: "上传中",
  extracting_metadata: "提取元信息",
  extracting_audio: "提取音频",
  transcribing: "语音转写",
  detecting_shots: "镜头切分",
  extracting_keyframes: "提取关键帧",
  extracting_structure: "结构拆解",
  analyzing_assets: "分析素材",
  mapping_slots: "槽位匹配",
  planning_completion: "缺口规划",
  generating_storyboard: "生成分镜",
  building_timeline: "构建时间线",
  rendering: "渲染视频",
  completed: "已完成",
  // P1 stages
  running_agent: "运行 AI 分析",
  generating_material: "生成补全素材",
  generating_image: "AI 生图",
  generating_video: "AI 生视频",
  generating_tts: "合成配音",
  rendering_material: "渲染包装片段",
  parsing_edit_intent: "理解改片指令",
  applying_edit_intent: "应用改片",
};
```

Also map `event.message` as primary line; stage label as subtitle.

### 6. ModelGatewayStatusPanel

Location: workbench header or `/projects` settings strip (alongside existing cookie panel pattern).

- Fetch `GET /api/settings/model-gateway` on mount.
- Show per-provider: ✅ 已配置 / ⚠️ 未配置 + model name when present.
- If any required provider missing (`text`, `image` at minimum for P1 demo): amber banner「模型服务未就绪，请在服务端配置环境变量」with link text listing env var names (no secrets).
- If `fixtureMode: true`: info badge「Fixture 模式」.

### 7. TaskArtifactPreview

Replace monospace-only artifact list in progress panel.

For each `artifactRefs[]` entry on latest TaskEvent:

| type | UI |
| --- | --- |
| `image` | thumbnail `<img>` via project media proxy or artifact URI helper |
| `video` | `<video controls>` small preview |
| `audio` | `<audio controls>` |
| `json` / `text` | collapsible snippet |
| `html` / `render` | link「打开预览」 |

- Append-only list during task (dedupe by `artifact.id`).
- Section title:「阶段产物」.
- When stage ∈ `{ generating_image, generating_video, generating_tts, rendering_material, generating_material }`, auto-expand section.

Implement `artifactDisplayUrl(projectId, ref: ArtifactRef)` in apiClient or lib helper consistent with existing sample media routes.

### 8. MultiTaskProgress (`useMultiTaskProgress`)

**Locked design** (matches multi-variant plan): one SSE/poll subscription **per taskId**.

```typescript
type TrackedTask = {
  taskId: string;
  generationId: string;
  variant: string;
  label: string; // from registry
};

function useMultiTaskProgress(tasks: TrackedTask[]): {
  byTaskId: Record<string, UseTaskProgressResult>;
  allTerminal: boolean;
  anyFailed: boolean;
};
```

`ProjectWorkbench` changes:

- Replace single `taskId` / `generationId` with `activeGenerations: TrackedTask[]` after `createGenerationPlan`.
- Render `MultiTaskProgressPanel`: one card per variant task.
- On all terminal + success: load each generation's plan; set active variant tab.
- sessionStorage: persist `{ activeGenerations, selectedVariant }` not single taskId.
- Retry: per-task retry button calling existing `POST /api/tasks/{taskId}/retry`.

Backward compat: if API returns legacy single `{ generationId, taskId }` (should not after multi-variant), wrap as one-item array.

### 9. AgentRunsDrawer (optional, demo-friendly)

- Button on result panel:「查看 AI 调用链」.
- Fetches `GET /api/generations/{id}/agent-runs`.
- Table: agentName, model, latencyMs, outputValid, promptVersion.

### 10. P1 error messages

Extend `formatTaskError` for codes:

| code | User hint |
| --- | --- |
| `gateway_not_configured` | 请在服务端配置模型 API 环境变量 |
| `video_quota_exceeded` | 本条生成已用完 1 次生视频配额 |
| `hyperframes_missing` | 未安装 HyperFrames CLI |
| `LLMValidationError` / schema fail | AI 输出格式异常，可重试 |

---

## Task Checklist

### Phase A

- [ ] **Task 1:** Extend apiClient + fixture-resolver for multi-variant, model-gateway, revise, agent-runs.
- [ ] **Task 2:** VariantPicker + VariantTabs + tests.
- [ ] **Task 3:** StructureEvidencePanel + analysis-stage messaging.
- [ ] **Task 4:** GeneratedAssetBadge + gap report / timeline integration.
- [ ] **Task 5:** ReviseInputBar + EditIntentList (fixture revise response).
- [ ] **Task 6:** Wire Phase A into ProjectWorkbench; P0 panels unchanged when P1 fields absent.

### Phase B (after backend gates)

- [ ] **Task 7:** `stageLabels.ts` + update TaskProgressPanel to use labels; update useTaskProgress tests.
- [ ] **Task 8:** ModelGatewayStatusPanel + fixture + test.
- [ ] **Task 9:** TaskArtifactPreview + integrate into TaskProgressPanel.
- [ ] **Task 10:** useMultiTaskProgress + MultiTaskProgressPanel + ProjectWorkbench migration + tests.
- [ ] **Task 11:** AgentRunsDrawer (optional but recommended for demo).
- [ ] **Task 12:** formatTaskError P1 codes + TaskProgressPanel failed-state hints.
- [ ] **Task 13:** End-to-end fixture-resolver paths for full P1 demo flow; ProjectWorkbench.test.tsx covers multi-task mock.

---

## Verification

```powershell
cd apps/web
npm run typecheck
npm run test
npm run build
```

Phase A can pass before Phase B tasks are implemented (skip or `@todo` Phase B tests until backend ready — prefer splitting test files).

---

## Acceptance Criteria

1. User can pick variants before generate; default both enabled variants selected.
2. Evidence panel shows keyframe + transcript when present in VideoStructure.
3. **All P1 task stages** show Chinese labels in progress UI (Phase B).
4. **During generation**, new image/video/audio artifacts appear in progress panel when `artifactRefs` update (Phase B).
5. **Two parallel tasks** show independent progress cards (Phase B, after multi-variant API).
6. ModelGateway status visible; missing config shows non-blocking warning (Phase B).
7. NL revise shows intents; multi-variant results in tabs.
8. P0 flows work when P1 fields absent.

---

## Commit Messages

Phase A:

```text
feat(web): P1 workbench evidence, variant picker, NL revise fixtures
```

Phase B:

```text
feat(web): P1 multi-task progress, artifact preview, model gateway status
```
