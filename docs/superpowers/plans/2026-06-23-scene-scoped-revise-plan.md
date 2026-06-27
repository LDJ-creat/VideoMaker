# Scene-scoped Revise (分镜级直改) — 2026-06-23

## 目标

在工作台分镜卡片上提供结构化改片入口，**跳过 `revise_planner` LLM**，直接生成确定性 `RevisePlan`，仍走 `RevisePlanCard` 确认 + `POST /revise/execute` 执行链路。

## Visual edit 双模式（v2）

单一入口 **「修改/重生成画面」**；用户显式选择：

| mode | 行为 |
|------|------|
| `edit` | 保留上游素材（Pexels / reuse / image），仅 invalidate 终端 HF；`material_author` 基于归档 `material-spec.json` 增量改 |
| `full` | 该 slot 整条 visual completion 链重跑（含 Pexels 重搜、AIGC 重生成、HF 全量 author） |

请求体：

```json
{
  "sceneId": "string",
  "slotId": "string",
  "mode": "edit | full",
  "instruction": "string (required, max 500)"
}
```

Intent params：`materialEditMode`, `editInstruction`, `requiresMaterialRegen: true`

## 槽位链类型

Worker `classify_slot_material_chain` 映射：`hf_only` / `stock_then_hf` / `reuse_then_hf` / `image_only` / …

归档路径：`generations/{id}/revise-material-archive/{slotId}/`（spec + composition + 可选 stock/reuse 底片）

## API

```http
POST /api/generations/{generationId}/revise/plan
```

请求体（**二选一**）：

- NL：`{ "instruction": "..." }`
- 结构化：`{ "structured": { "sceneId", "slotId", "mode", "instruction" } }`

## Worker

- `scene_revise_builder.py` — mode + instruction → intents
- `revise_material_edit.py` — 链分类、selective invalidate、归档/加载 spec
- `revise_scope.infer_material_scope` — scene-scoped `material_regen` → `scoped`

## Web

- `SceneRevisePanel` — edit/full 单选 + 必填修改说明
- `StoryboardSceneCard` — 「修改/重生成画面」入口

## 保留（非分镜直改 UI）

底部 NL 改片仍可使用 `packaging_scene_patch` / `subtitle_patch`（低成本 in_place）。

## 明确不在范围

| 能力 | 原因 |
|------|------|
| 调时长 | 全局 TTS 下只改 storyboard 时间窗会错位 |
| 改口播 | 需 master TTS + Whisper realign |

## 验证

```powershell
cd packages/contracts && npm run check && npm run validate:schemas
cd services/worker && python -m pytest tests/test_scene_revise_builder.py tests/test_revise_material_edit.py tests/test_revise_scope.py -q
cd services/api && python -m pytest tests/test_revise_plan_routes.py -q
cd apps/web && npm run test -- scene-revise-panel.test.tsx
```

E2E：`docs/demos/nl-revise-e2e-checklist.md` § Scene structured revise
