# Revise 改片降本三档落地方案

**Date:** 2026-06-10  
**Status:** Implemented

## Summary

NL revise execute 路径引入 scope 传播与三档成本路由：

| Tier | 路由 | 成本 | 素材 |
|------|------|------|------|
| 1 | `packaging_scene_patch` → in_place | 低 | 保留 `generated/` |
| 2 | `material_regen` + scoped fork | 中 | 仅失效/重跑 `affectedSlotIds` |
| 3 | `packaging_agent` packaging-only fork | 中低 | 保留 `generated/`，跳过 AIGC |

## Worker

- [`revise_scope.py`](../../../services/worker/app/pipelines/revise_scope.py) — `infer_material_scope`, `resolve_slot_ids_from_intents`
- [`intent_applier.py`](../../../services/worker/app/pipelines/intent_applier.py) — `ReviseContext.material_scope`, 阶段映射修正
- [`revise_pipeline.py`](../../../services/worker/app/pipelines/revise_pipeline.py) — 条件保留 `generated/`, scoped invalidate
- [`completion_registry.py`](../../../services/worker/app/providers/completion_registry.py) — `invalidate_material_for_slots`
- [`revise_patch_executor.py`](../../../services/worker/app/pipelines/revise_patch_executor.py) — `apply_packaging_scene_patch`, `sceneOverlays`
- [`revise_plan_builder.py`](../../../services/worker/app/pipelines/revise_plan_builder.py) — 规则分流 + `affectedSlotIds`

## Contracts

- `packaging_scene_patch` operation / executionTool
- `packagingPlan.sceneOverlays[]`
- `RevisePlan.affectedSlotIds`

## Verification

```powershell
cd packages/contracts
npm run check
npm run validate:schemas

cd services/worker
python -m pytest tests/test_revise_scope.py tests/test_packaging_scene_patch.py tests/test_invalidate_material_slots.py tests/test_revise_pipeline.py tests/test_revise_planner.py tests/test_intent_applier.py -q

cd services/api
python -m pytest tests/test_revise_plan_routes.py -q --basetemp=$env:TEMP/pytest-videomaker

cd apps/web
npm run typecheck
npm run test -- revise-plan-card.test.tsx
```

E2E: [`docs/demos/nl-revise-e2e-checklist.md`](../../demos/nl-revise-e2e-checklist.md)
