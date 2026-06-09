# NL Revise Planner, Patch Executor, and Session Plan

**Date:** 2026-06-09  
**Status:** Implemented

## Summary

Three-phase NL revise upgrade:

1. **Revise Planner + confirm UI** — `POST /revise/plan` before execution
2. **Patch executor** — `subtitle_patch` / `timeline_scene_patch` with `in_place` vs `fork` routing
3. **revise-session** — multi-turn context for planner inputs

## API

| Route | Purpose |
|-------|---------|
| `POST /api/generations/{id}/revise/plan` | Planner → draft `RevisePlan` + session turn |
| `POST /api/generations/{id}/revise/execute` | Approve plan; `in_place` patch or `fork` revise |
| `GET /api/generations/{id}/revise/session` | Session + recent plans |
| `POST /api/generations/{id}/revise/cancel` | Cancel draft plan(s) |
| `POST /api/generations/{id}/revise` | Legacy shortcut: plan + execute |

## Artifacts

```text
generations/{sourceGenerationId}/
  revise-session.json
  revise-plans/{planId}/plan.json
  revise-patches/{patchId}/   # in-place patch audit
```

## Worker

- `revise_planner` agent — schema `revise-planner-output`
- `revise_plan_builder.py` — rules fallback + plan enrichment
- `revise_patch_executor.py` — subtitle / timeline patches + re-render

## Verification

```powershell
cd services/api
python -m pytest tests/test_revise_plan_routes.py tests/test_revise_generation.py -v

cd ../worker
python -m pytest tests/test_revise_planner.py tests/test_subtitle_patch.py -v

cd ../../apps/web
npm run test -- revise-plan-card.test.tsx
```

E2E: `docs/demos/nl-revise-e2e-checklist.md`
