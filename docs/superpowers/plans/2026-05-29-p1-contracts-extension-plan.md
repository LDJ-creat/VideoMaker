# P1 Contracts Extension Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend shared contracts for P1: new schemas (`EditIntent`, `MaterialSpec`, `AgentRunLog`), extend existing schemas (`TaskEvent`, `AssetInventory`, `CompletionAction`, `RenderTimeline`), and add variant registry — without breaking P0 consumers.

**Architecture:** JSON Schema remains source of truth under `packages/contracts/schemas/`. TypeScript types in `src/types.ts` mirror schemas. Variant registry lives in `variants/registry.yaml` with a TS loader used by web and validated at worker startup.

**Tech Stack:** JSON Schema draft 2020-12, TypeScript, Node validate script, Python schema_loader (reads same files).

---

## Session Context (read first)

VideoMaker P0 is merged on `main`. Core contracts exist: `VideoStructure`, `AssetInventory`, `GapReport`, `GenerationPlan`, `RenderTimeline`, `TaskEvent`.

P1 master plan: `docs/superpowers/plans/2026-05-29-videomaker-p1-implementation-plan.md`.

**This plan is Wave 0 — must merge before all other P1 worktrees.** Every parallel stream depends on these schema names and enum extensions.

**Locked decisions:** No LiteLLM. Default variants `high_click`, `high_conversion`. Video gen quota field documented in types. No rule-based semantic fallback (types should allow new completion providers).

---

## Prerequisites

- P0 contracts package passes `npm run check` and `npm run validate:schemas`.
- Branch: `feature/p1-contracts-extension` from current `main`.

---

## Files Allowed To Change

**Create:**

- `packages/contracts/schemas/edit-intent.schema.json`
- `packages/contracts/schemas/material-spec.schema.json`
- `packages/contracts/schemas/agent-run-log.schema.json`
- `packages/contracts/variants/registry.yaml`
- `packages/contracts/src/variants.ts`
- `packages/contracts/tests/variants.test.ts` (if test runner exists; else validate in script)

**Modify:**

- `packages/contracts/schemas/task-event.schema.json` — add P1 stages
- `packages/contracts/schemas/asset-inventory.schema.json` — extend `CandidateMoment`
- `packages/contracts/schemas/gap-report.schema.json` — extend `CompletionAction`
- `packages/contracts/schemas/render-timeline.schema.json` — extend `generatedBy`
- `packages/contracts/src/types.ts`
- `packages/contracts/src/index.ts`
- `packages/contracts/scripts/validate-schemas.mjs` — validate registry yaml if feasible

**Out of scope:** `services/**`, `apps/**` (except re-export if needed — prefer not).

---

## Task 1: Extend TaskEvent stages

**Files:** Modify `task-event.schema.json`, `src/types.ts`

Add to `TaskStage` union:

```text
running_agent
generating_material
generating_image
generating_video
generating_tts
rendering_material
parsing_edit_intent
applying_edit_intent
```

- [ ] **Step 1:** Update JSON Schema enum for `stage`.
- [ ] **Step 2:** Update TS `TaskStage` type identically.
- [ ] **Step 3:** Run `npm run check`.

---

## Task 2: EditIntent schema

**Files:** Create `edit-intent.schema.json`, update `types.ts`

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "edit-intent",
  "type": "object",
  "required": ["intents"],
  "properties": {
    "intents": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["target", "operation", "params", "rationale"],
        "properties": {
          "target": {
            "type": "string",
            "enum": [
              "generation_plan.storyboard",
              "generation_plan.packaging",
              "render_timeline",
              "generation_params"
            ]
          },
          "operation": {
            "type": "string",
            "enum": [
              "adjust_hook",
              "reduce_subtitles",
              "increase_subtitles",
              "reorder_selling_points",
              "change_pace",
              "change_packaging_style",
              "adjust_cta"
            ]
          },
          "params": { "type": "object" },
          "rationale": { "type": "string" }
        }
      }
    }
  }
}
```

- [ ] **Step 1:** Add schema file.
- [ ] **Step 2:** Add `EditIntent`, `EditIntentItem` types.
- [ ] **Step 3:** Register in validate-schemas script file list.

---

## Task 3: MaterialSpec schema

**Files:** Create `material-spec.schema.json`, update `types.ts`

Required fields:

- `template`: enum `benefit-card` | `title-lower-third` | `ken-burns` | `custom`
- `durationSec`: number, minimum 0.5, maximum 30
- `params`: object with optional `title`, `bullets[]`, `colors`, `assetRefs[]`, `subtitle`

- [ ] **Step 1:** Write schema.
- [ ] **Step 2:** Add TS types `MaterialSpec`, `MaterialTemplate`.

---

## Task 4: AgentRunLog schema

**Files:** Create `agent-run-log.schema.json`, update `types.ts`

Fields:

```typescript
type AgentRunLog = {
  id: string;
  taskId?: string;
  generationId?: string;
  agentName: string;
  promptVersion: string;
  model: string;
  task: string;
  inputSummary: string;
  outputValid: boolean;
  validationErrors?: string[];
  latencyMs: number;
  tokenUsage?: { prompt: number; completion: number };
  createdAt: string;
};
```

- [ ] **Step 1:** Schema + types.
- [ ] **Step 2:** Ensure `$id` is `agent-run-log` for Python `validate_contract`.

---

## Task 5: Extend AssetInventory CandidateMoment

**Files:** Modify `asset-inventory.schema.json`, `types.ts`

Add optional fields on `CandidateMoment`:

- `visualTags: string[]`
- `highlightScore: number` (0–1)
- `suggestedSegmentRoles: Array<"hook" | "mid" | "cta">`

- [ ] **Step 1:** Extend schema without breaking existing fixtures.
- [ ] **Step 2:** Update TS type.

---

## Task 6: Extend CompletionAction and generatedBy

**Files:** Modify `gap-report.schema.json`, `render-timeline.schema.json`, `types.ts`

`CompletionAction` add:

- `provider`: enum `asset_reuse` | `hyperframes_material` | `image_generation` | `video_generation` | `tts` | `text_completion` | `packaging_completion`
- `rationale: string`
- `artifactRef?: ArtifactRef`

`TimelineClip.generatedBy` structure:

```typescript
type GeneratedBy = {
  provider: string;
  model?: string;
  promptVersion?: string;
  template?: string;
};
```

- [ ] **Step 1:** Update schemas (keep backward compatible — new fields optional).
- [ ] **Step 2:** Update types.

---

## Task 7: Variant registry

**Files:** Create `variants/registry.yaml`, `src/variants.ts`

Registry content per master plan §9.1 (`high_click`, `high_conversion` enabled; `fast_paced`, `premium` disabled).

`variants.ts` exports:

```typescript
export type VariantDefinition = {
  id: string;
  label: string;
  enabled: boolean;
  description: string;
  agentOverrides: Record<string, Record<string, unknown>>;
};

export function loadVariantRegistry(): VariantDefinition[];
export function getEnabledVariantIds(): string[];
export function assertVariantsAllowed(ids: string[]): void;
```

- [ ] **Step 1:** Create YAML.
- [ ] **Step 2:** Implement loader (read YAML at build — use `fs` in Node or embed JSON export; pick one approach and document in plan commit).
- [ ] **Step 3:** Export from `index.ts`.

---

## Task 8: Python schema_loader compatibility

**Files:** Verify `services/worker/app/validation/schema_loader.py` picks up new schemas automatically.

- [ ] **Step 1:** Run worker test `test_schema_loader.py` — extend to assert new schema names exist.
- [ ] **Step 2:** If worker tests fail due to contracts-only change, update test expectations in worker (minimal diff).

---

## Verification

```powershell
cd packages/contracts
npm run check
npm run validate:schemas

cd ../../services/worker
python -m pytest tests/test_schema_loader.py -v
```

---

## Acceptance Criteria

1. All new schemas validate and have matching TS types.
2. P0 schema validation still passes on existing fixture JSON.
3. `getEnabledVariantIds()` returns `["high_click", "high_conversion"]`.
4. No changes to runtime business logic outside contracts package (except schema_loader test).

---

## Commit Message

```text
feat(contracts): extend schemas and variant registry for P1
```
