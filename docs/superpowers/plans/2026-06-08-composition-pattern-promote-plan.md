# Composition Pattern Promote（方案 C）

**Status:** implemented  
**E2E checklist:** `docs/demos/composition-agent-e2e-checklist.md` § Pattern promote / Workbench UI

## Goal

After full generation completes and Result MP4 is visible, show HF composition drafts in **CompositionPatternPromotePanel**. User clicks **加入知识库** (confirm only; no score or toggles). Backend runs full promote pipeline: sanitize → `composition_pattern_author` → build + relint → publish to global knowledge.

## Published layout

`storage/knowledge/{categorySlug}/comp-{generationId}-{slotId}/`

| File | Role |
|------|------|
| `composition-skill.md` | LLM skill doc |
| `spec.template.json` | Generalized, relint-passed MaterialSpec |
| `spec.instance.json` | Original deposit instance |
| `entry-meta.json` | `entryKind=composition_pattern` |
| `lint-log.json` | Lint on generalized spec |
| `provenance.json` | Source generation/slot |
| `references/` | Copied from draft |

## API

```http
GET /api/generations/{generation_id}/composition-patterns
POST /api/projects/{project_id}/knowledge/composition/promote
```

Promote body: `{ "generationId", "slotId", "confirm": true }`.

Worker subprocess: `run_p0_task.py` `mode=composition_pattern_promote` → `prepare_promoted_pattern_bundle`; API then `promote_pattern` + SQLite insert (idempotent re-promote by entryId).

## Contracts

`packages/contracts/schemas/composition-pattern-promote-output.schema.json` — `CompositionPatternPromoteOutput`.

## Key modules

- `services/composition/composition/patterns/sanitize.py`
- `services/composition/composition/patterns/promote_prepare.py`
- `services/worker/app/agents/composition_pattern_author.py`
- `apps/web/features/knowledge/CompositionPatternPromotePanel.tsx`

## Out of scope (v1)

- Async promote task / SSE
- User score or generalization toggles
- generation-plan materialSpec summary injection
