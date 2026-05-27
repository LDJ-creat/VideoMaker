# Agent Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the contract-driven Agent generation pipeline that turns sample analysis artifacts and user brief/assets into `VideoStructure`, `AssetInventory`, `GapReport`, and `GenerationPlan`.

**Architecture:** Implement deterministic local planners first, with LLM adapters behind interfaces. Tests should use fixtures and fake model outputs. All model outputs must be schema-validated before use.

**Tech Stack:** Python 3.11, pytest, JSON Schema validation, prompt markdown files, shared contracts as schema files.

---

## Scope And Boundaries

Branch/worktree:

```powershell
git worktree add .worktrees/agent-generation -b feature/agent-generation main
```

Allowed to create/modify:

- `services/worker/app/agents/**`
- `services/worker/app/pipelines/structure_pipeline.py`
- `services/worker/app/pipelines/generation_pipeline.py`
- `services/worker/app/tools/llm_tool.py`
- `services/worker/tests/**`
- `packages/prompts/**`
- `docs/superpowers/plans/2026-05-27-agent-generation-plan.md`

Do not modify:

- `packages/contracts/**` unless explicitly stopped and approved
- `apps/web/**`
- `services/api/**`

## Task 1: Schema Loading And Validation

**Files:**
- Create: `services/worker/app/validation/schema_loader.py`
- Create: `services/worker/tests/test_schema_loader.py`

- [ ] Write failing tests that load every schema from `packages/contracts/schemas`.
- [ ] Implement schema discovery from repo root.
- [ ] Implement `validate_contract(name, payload)` returning structured validation errors.
- [ ] Run `python -m pytest`.
- [ ] Commit: `feat(agent): add contract schema validation`.

## Task 2: LLM Tool Boundary

**Files:**
- Create: `services/worker/app/tools/llm_tool.py`
- Create: `services/worker/tests/test_llm_tool.py`

- [ ] Write failing tests for fixture mode and missing API key behavior.
- [ ] Implement `LLMTool.generate_json(task, inputs, schema_name)` with fixture-backed local mode.
- [ ] Ensure raw model output and validation errors can be saved as artifacts by callers.
- [ ] Run `python -m pytest`.
- [ ] Commit: `feat(agent): add llm json tool boundary`.

## Task 3: Structure Extraction Pipeline

**Files:**
- Create: `packages/prompts/agents/structure_analyst.md`
- Create: `services/worker/app/pipelines/structure_pipeline.py`
- Create: `services/worker/tests/fixtures/sample_analysis.json`
- Create: `services/worker/tests/test_structure_pipeline.py`

- [ ] Write failing tests that turn sample analysis fixture into valid `VideoStructure`.
- [ ] Implement deterministic fallback structure extraction for tests.
- [ ] Add prompt instructing the model to migrate structure only, not copy sample content.
- [ ] Validate output against `video-structure.schema.json`.
- [ ] Run `python -m pytest`.
- [ ] Commit: `feat(agent): extract video structure`.

## Task 4: Asset Inventory And Slot Mapping

**Files:**
- Create: `packages/prompts/agents/slot_mapper.md`
- Create: `services/worker/app/pipelines/generation_pipeline.py`
- Create: `services/worker/tests/test_slot_mapping.py`

- [ ] Write failing tests for user brief to `AssetInventory`.
- [ ] Write failing tests for matching `StructureSlot` to assets by type and semantic tags.
- [ ] Implement deterministic `build_asset_inventory` and `map_slots`.
- [ ] Validate inventory against `asset-inventory.schema.json`.
- [ ] Run `python -m pytest`.
- [ ] Commit: `feat(agent): add inventory and slot mapping`.

## Task 5: Gap Report And Generation Plan

**Files:**
- Create: `packages/prompts/agents/gap_planner.md`
- Create: `packages/prompts/agents/storyboard_writer.md`
- Create: `packages/prompts/agents/packaging_designer.md`
- Modify: `services/worker/app/pipelines/generation_pipeline.py`
- Create: `services/worker/tests/test_generation_plan.py`

- [ ] Write failing tests for missing/weak slot detection.
- [ ] Implement P0 completion strategies: `text_completion`, `packaging_completion`, `asset_reuse`.
- [ ] Generate storyboard and `RenderTimeline`.
- [ ] Validate outputs against `gap-report.schema.json` and `generation-plan.schema.json`.
- [ ] Run `python -m pytest`.
- [ ] Commit: `feat(agent): generate gap report and generation plan`.

## Verification

Run before handoff:

```powershell
cd services/worker
python -m pytest
python -m compileall app
```

Also run:

```powershell
cd packages/contracts
npm run validate:schemas
```

