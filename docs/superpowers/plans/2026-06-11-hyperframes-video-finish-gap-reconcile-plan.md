# HyperFrames 视频润色 + LLM Reconcile Gap 决策

**Date:** 2026-06-11  
**Status:** Implemented on `main` workstream

## Summary

Introduces a two-stage gap decision model: `gap_planner` LLM proposes per-slot `completionMode`, `finishIntent`, and ordered `suggestedFixes`; Python `gap_reconcile.reconcile_provider_chain` merges LLM hints with hard rules and cost policy. After storyboard approval, `reconcile_gap_finish_from_storyboard` refines finish chains. HF polish execution always routes through **`material_author`** with `finishBrief` + base media `assetRefs`; ken-burns is fallback only.

## Cost policy (both variants)

`asset_reuse` → `stock_media_search` → `hyperframes_material` → `image_generation` → `video_generation` (must-use / quota exceptions only).

Registry `high_click` / `high_conversion` gap_planner overrides aligned: `stockMediaPriority: high`, `videoGenPriority: low`.

## Contracts

- `gap-report.schema.json`: `completionMode`, `finishIntent`, `reconcileNotes` on weak/missing items
- `generation-plan.schema.json`: `completionMode`, `finishIntent`, `finishBrief` on completion actions
- `AuthorRequest.finish_brief` in `services/composition/composition/types.py`

## Modules

| Module | Role |
|--------|------|
| `gap_reconcile.py` | LLM chain merge, `aigc_required`, cost reorder, mode enforcement |
| `gap_planner.py` | `apply_provider_reconciliation` |
| `storyboard_finish_reconcile.py` | Post-storyboard finish upgrade |
| `base_media_resolver.py` | Resolve slot base video/image after primary provider |
| `finish_brief.py` | Build `finishBrief` for material_author |
| `hyperframes_material_provider.py` | `-finish` actions → material_author + render |

## Verification

```powershell
cd packages/contracts; npm run check; npm run validate:schemas
cd services/worker; python -m pytest tests/test_gap_reconcile.py tests/test_gap_selection.py tests/test_generation_plan.py tests/test_hyperframes_material_provider.py tests/test_storyboard_finish_reconcile.py -q
cd services/worker; python -m compileall app
```

E2E: `docs/demos/pexels-stock-media-e2e-checklist.md` § 场景 5–7.
