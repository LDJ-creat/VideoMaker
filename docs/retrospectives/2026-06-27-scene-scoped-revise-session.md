# 会话复盘：分镜 scoped 改片、结果页旧片与 timeline 重渲染

> **会话背景**：项目 `7bed327a-…` 上对 slot-6 做「画面居中」分镜改片（generation fork `0775c3a5-…`，task `ea2e937d-…`）；联调 plan 回写、ACP edit、进度 65% 卡住、retry 竞态、结果页仍显示源片 `47bf4406`、以及重渲染后 timeline clip 时间倒置导致劣质 MP4。  
> **文档用途**：项目复盘、排障清单、面试中讲述「改片 fork 全链路 + 前后端状态一致性」的案例。

---

## 1. 问题总览（按严重程度）

| # | 现象 | 根因类别 | 最终状态 |
|---|------|----------|----------|
| 1 | 改片成功后结果页 MP4 仍指向源片 `47bf4406` | 前端 hydrate 用旧 generation-run 覆盖 latest fork | 已修复 |
| 2 | 任务 100% 但 slot-6 居中不明显 / 成片 ~156KB 无音轨 | timeline `clip-slot-6` 时间倒置；fork render materials 缺 master.wav | 已修复（timeline + 手工补 materials 后重渲染） |
| 3 | 进度卡在 65%，slot-6 素材已就绪无后续提示 | 素材完成但 stage 仍 `generating_material`；cancel/retry 双 worker | 已缓解（提示文案 + 既有 cancel 杀进程） |
| 4 | scoped revise resume 未重算 timeline | `sync_timeline_to_narration` 无 WAV 时提前返回；resume 跳过 apply_material | 已修复 |
| 5 | 生成历史看不到改片 fork | fork 无 `generation_run_id`，未进 batch 列表 | 已修复（`revise-generations` API + UI） |
| 6 | `material-state.json` 的 `completedActionIds` 仍为空 | 历史竞态 / 持久化路径（与前序会话同源） | 部分缓解（磁盘推断 + scoped done 检查） |

---

## 2. 案例一：结果页加载旧片（前端）

### 现象

任务 `ea2e937d` 已成功，`0775c3a5` 的 `output.mp4` 存在，但工作台 **结果** 区视频 URL 仍指向 `47bf4406`（6/23 批次）。

### 根因

1. `loadProjectResults()` 先从 `GET .../generations/latest` 加载 fork。
2. Session 中 `activeGenerationRunId` 触发 `loadGenerationRunView()`，用 6/23 旧 run **整表替换** `variantPlans` / `activeGenerations`。
3. 改片 fork 不在 `generation-runs` 列表，用户点历史「查看结果」也会回到源 batch。

### 解决方案

- `reloadGenerationRunResults.ts`：`mergeActiveGenerationsByVariant`、`pickPreferredGenerationEntry`。
- `ProjectWorkbench.tsx`：hydrate **不再自动** `loadGenerationRunView`；改片 terminal 用 **event.taskId** 定位 fork；`loadGenerationIntoVariants` merge 而非覆盖。
- 新增 `GET /api/projects/{id}/revise-generations` + 生成历史 **改片结果** 区块。

### 关键文件

- `apps/web/features/workbench/ProjectWorkbench.tsx`
- `apps/web/lib/reloadGenerationRunResults.ts`
- `apps/web/features/generation-runs/GenerationRunHistoryPanel.tsx`
- `services/api/app/routers/sample_selection.py`

### 可复述要点

> 长任务 UI 的「最新业务 ID」与「用户上次查看的历史 run」是两种状态源；hydrate 时必须 **merge per variant**，不能把 history 视图当成 authoritative snapshot 覆盖 fork。

---

## 3. 案例二：timeline clip 时间倒置导致劣质成片

### 现象

`generation-plan.json` 中 storyboard slot-6 正常（21.4–24.2s），但 timeline `clip-slot-6` 为 `startSec=41.325 > endSec=34.316`。重渲染产出 ~138KB、仅视频轨、时长异常。

Worker stderr：`global TTS subtitles skipped: no vo-master clip or master.wav`。

### 根因（多层）

1. **`sync_timeline_to_narration` 依赖 narration WAV**  
   fork 的 `renders/0775.../materials/` 仅有 `action-slot-6.mp4`，无 `master.wav` → `narration_end_sec` 为空 → **整段 sync 跳过**，clip 时间永不从 storyboard 刷新。

2. **`_hold_tail` 早退路径**  
   计划时长已覆盖 narration 时直接 return，未调用 `_apply_storyboard_to_timeline_clips`（已在同会话修复）。

3. **scoped revise resume 跳过 plan 回写**  
   `material_skipped` 分支仅 `material_scope=none` 时 `sync_material_results_to_plan`；scoped edit 只 emit「materials ready」不写回 timeline。

4. **fork render staging 不完整**  
   改片仅重生成 slot-6，未复制源片其余 slot 的 staging materials；FFmpeg 只能拼出残缺时间线。

### 解决方案

| 层级 | 改动 |
|------|------|
| Worker | 新增 `scene_timing.normalize_scene_start_end`、`refresh_timeline_clip_timing()`（不依赖 WAV） |
| Worker | `apply_material_results_to_plan` / 渲染前强制 `refresh_timeline_clip_timing` |
| Worker | resume 时 **始终** `sync_material_results_to_plan`；修正 `sync_material_results_to_plan` 的 `render_root` 路径 |
| Worker | `revise_material_edit.py`：归档/加载 spec、plan rebind、storyboard timing 归一化 |
| 运维 | 重渲染前从源 generation 复制除 slot-6 外的 `renders/.../materials/*`，再删 output + retry |

### 关键文件

- `services/worker/app/pipelines/narration_timeline.py`
- `services/worker/app/pipelines/scene_timing.py`
- `services/worker/app/providers/completion_registry.py`
- `services/worker/app/pipelines/p0_demo_pipeline.py`
- `services/worker/app/pipelines/revise_material_edit.py`

### 验证（generation `0775c3a5`）

```powershell
# timeline clip 应为 21.409–24.171
python -c "import json; p=r'services/api/storage/projects/.../generations/0775.../generation-plan.json'; ..."

# 重渲染后 ffprobe：约 2.4MB、34.3s、含 audio
ffprobe -show_entries format=duration,size:stream=codec_type renders/0775.../output.mp4
```

### 可复述要点

> 改片 fork 是 **部分失效图**：storyboard/plan 更新了，但 timeline clip 与 render staging 仍可能是源 generation 的副本。任何「只改一个 slot」的路径都必须 explicit：**回写 plan timeline** + **staging 要么全量复制要么全量重跑**。

---

## 4. 案例三：分镜 scoped 改片（功能主线）

### 背景

跳过 `revise_planner` LLM，从分镜卡片结构化提交 `edit | full` + instruction，走既有 `RevisePlanCard` → execute。

### 技术决策

| 决策 | 备选 | 选择 | 理由 |
|------|------|------|------|
| Visual edit 模式 | 仅 full regen | `edit` 保留上游 + 仅 HF finish | 降本、保留 Pexels/复用底片 |
| Plan 确认 UI | 新面板 | 复用 `RevisePlanCard` | 与 NL revise 一致 |
| Fork 与 batch 关系 | 写入 generation_run | 独立 fork + `revise-context.json` | 改片不应污染原 batch 快照 |
| Timeline 同步时机 | 仅 rendering | material apply + render 前双刷 | 避免无 WAV 时 silent skip |

### 架构（改片 fork 数据流）

```text
源 generation 47bf4406
  └─ seed_revise_generation → fork 0775c3a5 (+ revise-context.json)
       ├─ scoped invalidate slot-6 (+ archive spec for edit mode)
       ├─ ACP/HF material_author (edit brief 含「居中」)
       ├─ apply_material / refresh_timeline_clip_timing
       └─ FFmpeg render → renders/0775.../output.mp4

前端：
  GET generations/latest (merge per variant)
  ≠ GET generation-runs/{old-run}  ← 不可覆盖 fork
  + GET revise-generations（改片历史入口）
```

### 关键文件

- `services/worker/app/pipelines/scene_revise_builder.py`
- `services/worker/app/pipelines/revise_material_edit.py`
- `services/api/app/routers/generations.py`（structured plan）
- `apps/web/features/nl-revise/SceneRevisePanel.tsx`

---

## 5. 配置与运维备忘

**手动触发 fork 重渲染（任务已成功、output 存在时）**

1. 删除 `renders/{forkId}/output.mp4`
2. checkpoint 移除 `rendering`（建议同时移除 `building_timeline`）
3. 确认 `renders/{forkId}/materials/` 含 **master.wav** 及未改 slot 的 mp4（可从源 generation 复制）
4. `POST /api/tasks/{taskId}/retry`（`succeeded` 且 render 缺失时 API 允许 retry）

**排障检查清单**

1. 结果 URL 代数：`variantPlans[activeTab].renderVideoUrl` 是否含 forkId？
2. `generation-plan.json` 中 `clip-{slotId}` 的 start/end 是否与 storyboard 一致？
3. `ffprobe` 是否同时有 video + audio stream？
4. Session 是否误触 `loadGenerationRunView` 加载旧 batch？

---

## 6. 测试与验证

```powershell
cd packages/contracts
npm run check && npm run validate:schemas

cd services/worker
python -m pytest tests/test_scene_revise_builder.py tests/test_revise_material_edit.py tests/test_revise_scope.py tests/test_narration_timeline.py -q

cd services/api
python -m pytest tests/test_revise_plan_routes.py tests/test_sample_selection_routes.py::test_list_revise_generations_returns_fork_with_context -q

cd apps/web
npm run test -- scene-revise-panel.test.tsx reload-generation-run-results.test.ts parallelMaterialActivity.test.ts
```

**手工 E2E**：`docs/demos/nl-revise-e2e-checklist.md` § Scene structured revise

---

## 7. 常见问题（Q&A）

### Q1：改片成功为什么历史里只有 6/23 批次？

**A**：batch run 只记录 `POST generation-plan` 触发的双变体任务；scoped revise fork 的 `generation_run_id` 为 NULL。请用 **改片结果** 列表或 **高转化版** tab（latest per variant）。

### Q2：retry 返回 400「cannot be retried」？

**A**：`succeeded` 且 `output.mp4` 非空时不可 retry。需先删 output（或走 render_incomplete 路径）。

### Q3：65% 卡住但磁盘已有 slot mp4？

**A**：看 SSE stage 是否仍为 `generating_material`；可能是合成/渲染未开始，或 cancel/retry 竞态。等 worker 退出后再 retry。

---

## 8. 遗留风险与后续改进

1. **fork 自动复制源 render materials**：scoped revise seed 或 rendering 前应复制未改 slot 的 staging，避免手工补文件。
2. **`completedActionIds` 持久化**：与 cancel/retry 竞态相关，需单写者或文件锁一致性（`RLock` 已部分缓解）。
3. **改片 fork 入库 generation_run（可选）**：若产品需要统一时间线，可增加 `reviseRun` 元数据而非复用 batch。
4. **无音轨成片自动检测**：render 完成后校验 audio stream，失败则 task 标记 failed 而非 succeeded。

---

*文档版本：2026-06-27 · 对应会话：scene-scoped-revise · fork 0775c3a5 · slot-6 居中*
