# 改片 Material Review Gate 方案

**Status:** Implemented (pending merge)  
**Depends on:** `docs/superpowers/plans/2026-06-29-material-review-gate-plan.md`

## 目标

将首次生成已实现的 Material Review Gate（LLM `material_reviewer` + 人工预览审核）扩展到 fork 改片链路，重点覆盖全片拆解单镜 `material_regen`；与 master/storyboard 人工审核解耦，未改 slot 继承原审核状态。

## 行为摘要

| 场景 | Material gate |
|------|---------------|
| 首次生成 + `human_review_mode=true` | 启用（visual_only → pause → approve → assembly） |
| Fork `material_regen`（scoped/all） | 启用（默认） |
| Fork `materialScope=none`（packaging-only） | 不启用 |
| `executionMode=in_place` patch | 不启用 |
| `VIDEOMAKER_MATERIAL_REVIEW_ON_REVISE=false` | 改片恢复直通 render |

Fork 改片保持 `human_review_mode=false`（不恢复 master/分镜 gate）。

## 核心实现

### Gate 判定

`services/worker/app/pipelines/material_review.py`:

- `material_review_on_revise_enabled()` — env `VIDEOMAKER_MATERIAL_REVIEW_ON_REVISE`（默认 `true`）
- `use_material_review_gate(human_review, revise_context)` — 首次生成靠 `human_review`；fork 在 `material_scope != none` 且 `generating_material` 在 affected stages 时启用

`p0_demo_pipeline.run_generation` 使用 `use_material_review_gate` 驱动 `visual_only` / `master_only` 两阶段与 `awaiting_material_review` 暂停。

### Fork seed 重置

`services/worker/app/pipelines/material_review_revise.py`:

- `reset_material_review_for_revise_fork()` — scoped 仅 reset 受影响 slot；`full_reset` 清空全部
- 未受影响 slot 保留 source 复制的 `agent_passed` + report

`revise_pipeline.seed_revise_generation` 在 invalidate 后调用 reset；`revise-context.json` 增加 `materialReviewScope`、`materialReviewSlotIds`、`sourceGenerationId`。

### API / Web

- `GET /api/generations/{id}/material-review` 响应可选 `reviseContext: { scope, affectedSlotIds, sourceGenerationId }`
- `RevisePlanCard`：fork + `material_regen` 提示将暂停素材审核（仅当 `materialReviewGateExpected=true`）
- `MaterialReviewPanel`：改片 banner、默认选中 affected slot、「继承/改片」标签

Gate 内单 slot NL 改片：`POST .../material-slots/{slotId}/revise`（同 generationId，不 fork）。

## Env

| Env | 含义 | Default |
|-----|------|---------|
| `VIDEOMAKER_MATERIAL_REVIEW_ON_REVISE` | fork 改片是否启用 material gate | `true` |

CI/fixture 可与 `VIDEOMAKER_MATERIAL_REVIEW_ENABLED=false` 组合跳过。

## 测试

| 文件 | 覆盖 |
|------|------|
| `services/worker/tests/test_revise_material_review.py` | gate 判定、seed reset、revise-context |
| `services/worker/tests/test_revise_pipeline.py` | scoped regen 暂停 `awaiting_material_review` |
| `services/api/tests/test_material_review_routes.py` | GET `reviseContext`、approve retry |
| `apps/web/tests/material-review-panel.test.tsx` | affected slot UX |
| `apps/web/tests/revise-plan-card.test.tsx` | fork material_regen 文案 |

E2E：`docs/demos/material-review-gate-e2e-checklist.md` § Revise fork。

## 文件清单

| 模块 | 文件 |
|------|------|
| Worker | `material_review.py`, `material_review_revise.py`, `revise_pipeline.py`, `p0_demo_pipeline.py` |
| API | `routers/generations.py` |
| Web | `MaterialReviewPanel.tsx`, `RevisePlanCard.tsx`, `apiClient.ts` |
