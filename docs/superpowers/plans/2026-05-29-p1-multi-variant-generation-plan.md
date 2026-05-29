# P1 Multi-Variant Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Support generating two default variants (`high_click`, `high_conversion`) in one API call, with registry-driven agent overrides and **parallel worker tasks** — with an explicit **frontend contract** for multi-task progress.

**Architecture:** API accepts `variants: string[]`; creates N generation records sharing structure/inventory; dispatches **N separate tasks**. Each task applies variant `agentOverrides` to StoryboardWriter, GapPlanner, PackagingDesigner.

**Tech Stack:** FastAPI, SQLite generations table, variant registry from contracts, worker generation pipeline.

---

## Session Context

**Depends on:**

1. `feature/p1-semantic-mapping-gap`
2. `feature/p1-aigc-material-completion` + `feature/p1-hyperframes-material` merged

**Master plan:** §9.

**Branch:** `feature/p1-multi-variant-generation`

**Downstream:** `p1-web-workbench` Phase B Task 10 depends on this API shape.

---

## Files Allowed To Change

**Create:**

```text
services/worker/app/config/variants.py
services/api/tests/test_multi_variant_generation.py
services/worker/tests/test_variant_overrides.py
```

**Modify:**

```text
services/api/app/routers/projects.py
services/api/app/schemas/generation.py        # if exists
services/api/app/services/generation_service.py
services/worker/app/pipelines/generation_pipeline.py
services/worker/app/pipelines/p0_demo_pipeline.py
services/worker/app/agents/storyboard_writer.py
services/worker/app/agents/gap_planner.py
services/worker/app/agents/packaging_designer.py
```

**Out of scope:** Full web UI (web plan). Must document frontend contract below.

---

## API Contract

### Request

```http
POST /api/projects/{project_id}/generation-plan
Content-Type: application/json

{
  "variants": ["high_click", "high_conversion"]
}
```

Default when body empty or field omitted: `["high_click", "high_conversion"]`.

Validation: reject unknown IDs or `enabled: false` variants with 400.

### Response (breaking change from P0)

P0 returned a single object `{ generationId, taskId, ... }`. P1 **must** return:

```json
{
  "generations": [
    {
      "generationId": "gen-abc",
      "variant": "high_click",
      "taskId": "task-abc",
      "label": "高点击版"
    },
    {
      "generationId": "gen-def",
      "variant": "high_conversion",
      "taskId": "task-def",
      "label": "高转化版"
    }
  ]
}
```

- `label` from variant registry (optional but recommended for web).
- Order matches request `variants` array order.

**Decision (locked):** **Separate task per variant** — not single orchestrator task. Rationale: independent SSE/retry/checkpoint per variant.

---

## Frontend Contract (required for web-workbench)

Web workbench **must not** assume a single `taskId` after generation.

### Subscription model (locked)

- Frontend opens **one SSE (or poll fallback) per `taskId`** in `generations[]`.
- No batch SSE endpoint in P1 — keep P0 task API unchanged.
- Each TaskEvent includes only its own `taskId`; web maps by id.

### ProjectWorkbench state

```typescript
type ActiveGeneration = {
  generationId: string;
  variant: string;
  taskId: string;
  label: string;
};
```

After `POST generation-plan`:

1. Store `activeGenerations: ActiveGeneration[]`.
2. Subscribe progress for all taskIds.
3. UI shows N progress cards until all terminal.
4. On success, fetch each `GET /api/generations/{generationId}` (or existing latest-per-variant helper).

### Latest generation API

Implement **one** of (pick in Task 2, document in API):

**Option A (recommended):** extend existing latest route:

```http
GET /api/projects/{project_id}/generations/latest
```

Response P1 shape:

```json
{
  "generations": [
    { "generationId": "...", "variant": "high_click", "plan": { ... } },
    { "generationId": "...", "variant": "high_conversion", "plan": { ... } }
  ]
}
```

**Option B:** keep single latest + add query:

```http
GET /api/projects/{project_id}/generations/latest?variant=high_click
```

If choosing Option B, web must call twice on reload — document in plan commit.

### Backward compatibility

- API tests must assert old clients sending empty body still get 2 generations (default variants).
- Web Phase A fixtures use new array shape only.

---

## Worker Job Payload

```json
{
  "projectId": "...",
  "generationId": "...",
  "variant": "high_click",
  "variantOverrides": {
    "storyboard_writer": { "hookStrength": "high", "tempo": "fast" },
    "gap_planner": { "preferProviders": ["hyperframes_material", "video_generation"] }
  }
}
```

Pipeline passes `variantOverrides` into every Agent call `inputs` dict.

---

## Shared vs Forked Artifacts

| Artifact | Shared? |
| --- | --- |
| VideoStructure | Yes — read-only |
| AssetInventory base | Yes |
| SlotMapper output | May run once per project batch (optimization); GapPlanner per variant |
| GapReport | No — per generationId |
| GenerationPlan | No |
| RenderTimeline | No |
| Material outputs | No |
| VideoGenQuota | **No** — each generationId gets its own quota=1 |

Checkpoint path unchanged: `generations/{generationId}/checkpoint.json`.

---

## TaskEvent / artifactRefs

Each variant task emits its own events. When material stages complete, include `artifactRefs` for generated clips so web `TaskArtifactPreview` can show per-variant previews.

Worker must not mix artifact refs across generationIds.

---

## StoryboardWriter Overrides

Append variant-specific instructions to user message (see registry `agentOverrides`).

---

## Task Checklist

- [ ] **Task 1:** Python `variants.py` loads registry; tests for enabled IDs.
- [ ] **Task 2:** API accepts variants array; returns `generations[]`; **choose and implement** latest-generation reload strategy (Option A or B).
- [ ] **Task 3:** Worker reads variant + overrides from task payload.
- [ ] **Task 4:** Per-generation VideoGenQuota (not shared across variants).
- [ ] **Task 5:** test_variant_overrides — different gap provider preference per variant in fixture scenario.
- [ ] **Task 6:** API test: 2 variants → 2 distinct taskIds + generationIds; update `test_p0_flow_routes.py` expectations.
- [ ] **Task 7:** Document response shape in plan + comment in router for frontend consumers.

---

## Verification

```powershell
cd services/api
python -m pytest tests/test_multi_variant_generation.py tests/test_p0_flow_routes.py -v

cd ../worker
python -m pytest tests/test_variant_overrides.py -v
```

---

## Acceptance Criteria

1. Single API call spawns N generations and N tasks (default N=2).
2. Invalid variant returns 400.
3. Each generation isolated under `generations/{generationId}/`.
4. Frontend contract documented; latest reload works for all active variants.
5. Each variant has independent video generation quota.

---

## Commit Message

```text
feat(api): multi-variant generation with parallel tasks and frontend contract
```
