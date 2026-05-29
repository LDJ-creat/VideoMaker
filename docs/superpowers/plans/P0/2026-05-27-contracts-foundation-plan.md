# Contracts Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create the shared P0 contracts package for VideoMaker so frontend, API, worker, Agent, and renderer can develop against stable schemas and TypeScript types.

**Architecture:** Store JSON Schemas under `packages/contracts/schemas`, TypeScript domain types under `packages/contracts/src/types.ts`, and a lightweight Node validator under `packages/contracts/scripts/validate-schemas.mjs`. The package is intentionally dependency-light and does not depend on frontend or backend code.

**Tech Stack:** TypeScript, JSON Schema draft 2020-12, Node.js.

---

### Task 1: Contracts Package Skeleton

**Files:**
- Create: `packages/contracts/package.json`
- Create: `packages/contracts/tsconfig.json`
- Create: `packages/contracts/src/index.ts`

- [x] **Step 1: Create package manifest**

Create a private package with `check` and `validate:schemas` scripts.

- [x] **Step 2: Create TypeScript config**

Create a strict TypeScript config that emits declarations only when `build` is run.

- [x] **Step 3: Create index export**

Export all contract types from `src/types.ts`.

### Task 2: JSON Schema Contracts

**Files:**
- Create: `packages/contracts/schemas/artifact-ref.schema.json`
- Create: `packages/contracts/schemas/tool-error.schema.json`
- Create: `packages/contracts/schemas/task-event.schema.json`
- Create: `packages/contracts/schemas/video-structure.schema.json`
- Create: `packages/contracts/schemas/asset-inventory.schema.json`
- Create: `packages/contracts/schemas/gap-report.schema.json`
- Create: `packages/contracts/schemas/generation-plan.schema.json`
- Create: `packages/contracts/schemas/render-timeline.schema.json`

- [x] **Step 1: Define shared infrastructure schemas**

Create `ArtifactRef`, `ToolError`, and `TaskEvent`.

- [x] **Step 2: Define analysis and structure schemas**

Create `VideoStructure` with metadata, narrative, rhythm, packaging, slots, evidence, and confidence.

- [x] **Step 3: Define generation schemas**

Create `AssetInventory`, `GapReport`, `GenerationPlan`, and `RenderTimeline`.

### Task 3: TypeScript Domain Types

**Files:**
- Create: `packages/contracts/src/types.ts`

- [x] **Step 1: Add shared primitive and task types**

Define artifact, task, tool error, and progress event types.

- [x] **Step 2: Add video structure types**

Define metadata, narrative, rhythm, packaging, and slot types.

- [x] **Step 3: Add asset, gap, generation, and timeline types**

Define inventory, matching, completion, storyboard, generation, and render timeline types.

### Task 4: Schema Validation Script

**Files:**
- Create: `packages/contracts/scripts/validate-schemas.mjs`

- [x] **Step 1: Load all schema files**

Read every `*.schema.json` file from `schemas`.

- [x] **Step 2: Validate JSON syntax and required metadata**

Fail if a schema lacks `$schema`, `$id`, `title`, or `type`.

- [x] **Step 3: Wire package script**

Expose the script as `npm run validate:schemas`.

### Task 5: Verification

**Files:**
- Modify: `docs/superpowers/plans/2026-05-27-contracts-foundation-plan.md`

- [x] **Step 1: Run TypeScript check**

Run `npm run check` inside `packages/contracts`.

- [x] **Step 2: Run schema validation**

Run `npm run validate:schemas` inside `packages/contracts`.

- [x] **Step 3: Commit**

Commit the plan and contracts implementation.
