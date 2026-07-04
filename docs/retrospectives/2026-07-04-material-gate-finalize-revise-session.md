# 会话复盘：Material Gate Finalize 职责拆分与改片/进度修复

> **会话背景**：项目 `7bed327a-…`、generation `5d5f3ec4-…`（`high_conversion`）；素材审核 gate 已上线，但在 slot-6 NL 改片、重试、前端进度与错误展示上暴露多条链路问题。用户最终完成全片生成验证。  
> **文档用途**：理解 **in-session review** 与 **material gate finalize** 的分工；排查 gate 内改片、重试、前端 stale 错误；面试/分享「审片零 LLM finalize」设计。

---

## 1. 问题总览

| # | 现象 | 根因类别 | 最终状态 |
|---|------|----------|----------|
| 1 | gate 内 NL 改片后 ACP 未按用户指令修 layout/动效 | revise 上下文嵌套在 `materialGateRevise`，加载器只读顶层字段 | 已修复 |
| 2 | post-session 与 in-session 重复调 `material_reviewer`，结论分裂 | finalize 路径仍跑 LLM review | 已重构（gate finalize 零 LLM） |
| 3 | slot-6 retry 显示「AI 视频生成 403」，但计划为 HF-only | 前端/任务历史展示 **stale** 的 slot-1 `video_generation_failed`；真实失败为底片 staging | 已解释；staging 待持续改进 |
| 4 | 改片/重试失败后前端仍「生成中」，需刷新才见 failed | SSE 在 rejected terminal 事件时仍停监听；`retrying` override 盖住 `failed` | 已修复 |
| 5 | 素材 gate 重试报 `missing sourceGenerationId` | `retry_task` 见 `revise-context.json` 即走 fork revise，gate 原地改片无 `sourceGenerationId` | 已修复 |
| 6 | packaging slot（cta）计划 `source_then_polish` 但执行链仅 HF | `high_conversion` variant + reconcile 对 packaging 强制 HF-only，与 storyboard mode 不一致 | 已修复（新 gap/plan 生效） |

---

## 2. 案例一：In-session Review 与 Gate Finalize 职责拆分

### 背景

Material Review Gate（2026-06-29）在 author session 内通过 `review_material_preview` 调 `material_reviewer`（video / vision / text 路由）。原 `material_review_finalize.py` 在 session 结束后 **再次** 调 `run_slot_review()`，导致：

- 重复 LLM 成本与延迟  
- in-session marker 与 `material-reviews/{slotId}/report.json` 结论可能不一致  
- UI 只读 finalize 报告时，in-session 审核结论被架空  

### 最终架构

```text
┌─ In-session（ACP/ReAct author）──────────────────────────────┐
│  lint → scratch preview.mp4 → LLM review (material_reviewer) │
│    ├─ 通过 → material-review-marker.json (approved + specHash)│
│    ├─ 未通过 → repair followup（turn < max_turns）            │
│    └─ max_turns 用尽 → session 结束（scratch 保留最后一轮）   │
│  ※ 不写 generated/                                           │
└──────────────────────────┬───────────────────────────────────┘
                           ▼
┌─ Material Gate Finalize（session 后，零 LLM）─────────────────┐
│  1. materialize_final → copy preview 或 render → generated/*.mp4│
│  2. promote marker → material-reviews/（reviewPhase=promoted）│
│  3. 更新 material-review-state（agent_passed | agent_failed） │
└──────────────────────────┬───────────────────────────────────┘
                           ▼
              awaiting_material_review（人工 gate）
```

### 命名对照

| 旧称 | 新称 / 模块 |
|------|-------------|
| post-session review | **material gate finalize** |
| `persist_slot_material_review()` | `finalize_slot_material_gate()` |
| `finalize_visual_material_reviews()` | `finalize_visual_material_gate()` |
| LLM 审片在 finalize | **禁止**；仅 promote in-session marker |

### 双决策分离

| 函数 | 语义 | 宽/严 |
|------|------|-------|
| `should_materialize_final()` | 有 preview 或 spec 则把 MP4 就位到 `generated/` | **宽** — 失败也出片 |
| `should_promote_as_passed()` | marker.approved && specHash 一致 → `agent_passed` | **严** — 决定 gate 默认态 |

Promote 报告字段：`reviewPhase: "promoted"`、`reviewInputs.reviewReuse: "in_session"`、`trace.reviewRoute: "promoted"`。

### Gate 内改片默认关闭 in-session review

`VIDEOMAKER_MATERIAL_REVIEW_ACP_IN_SESSION_REVISE` 默认 `false`：NL 改片重跑 author 时不重复 LLM 审片，finalize 仍 materialize + promote。

### 关键文件

- `services/worker/app/pipelines/material_gate_promote.py` — materialize + marker promote  
- `services/worker/app/pipelines/material_gate_finalize.py` — 零 LLM finalize  
- `services/worker/app/pipelines/material_review_finalize.py` — 薄 re-export 层  
- `services/worker/app/providers/hyperframes_material_provider.py` — author 结束后调 finalize  
- `docs/superpowers/plans/2026-07-04-material-gate-finalize-plan.md` — 可执行规格  

### 可复述要点

> 审片是 **创作循环**（in-session，可 repair）；finalize 是 **产物就位 + 状态机推进**（零 LLM）。把「有没有 MP4」和「agent 是否通过」拆开，用户才能在 `agent_failed` 时仍看片、NL 改片或人工 override。

---

## 3. 案例二：Gate 改片 NL 指令未进 ACP

### 现象

素材 gate 对 slot-6 提交 NL 改片（居中布局、按钮缩放动效）后，ACP 产出与首次生成几乎相同，未体现修改要求。

### 根因

API 写入 `revise-context.json` 时使用嵌套结构：

```json
{ "materialGateRevise": { "editInstruction": "...", "affectedSlotIds": ["slot-6"] } }
```

`load_revise_material_edit_context()` 原先只读顶层 `materialEditMode` / `editInstruction`，返回 `None`，导致 `hyperframes_material_provider` 与 ACP `task.json` 缺少 `editInstruction` / `existingMaterialSpec` 编辑上下文。

### 解决方案

- `normalize_material_edit_context()` — 合并顶层与 `materialGateRevise` 嵌套字段  
- `material_edit_context_applies_to_slot()` — 按 `affectedSlotIds` 过滤  
- ACP `scratch_assets` / `author_payload` 透传 `materialGateRevise` 与 `reviseContext`  
- `compositionAuthorBrief.authorPrompt` 追加修改要求（`build_edit_finish_brief`）

### 关键文件

- `services/worker/app/pipelines/revise_material_edit.py`  
- `services/worker/app/providers/hyperframes_material_provider.py`  
- `services/worker/app/composition/acp/author.py`  
- `services/worker/app/composition/acp/scratch_assets.py`  

---

## 4. 案例三：前端失败态不同步与 Stale 错误

### 现象 A — 进度卡在「生成中」

改片/重试失败后需手动刷新才看到 failed。

### 根因 A

1. `generationStatusOverrides.retrying` 在 `resolveLiveTaskStatus` 中覆盖 terminal `failed`  
2. `shouldAcceptTaskEventUpdate` 因时间戳拒绝较旧的 `failed` 事件  
3. `startTaskWatch` 收到 terminal 事件即停止 SSE，即使 `applyEvent` 未成功合并  

### 解决方案 A

- Terminal 态优先于 optimistic override（`taskMilestones.ts`）  
- active → terminal 事件始终接受（`taskEventMerge.ts`）  
- 仅当 `applyEvent` 成功才停止监听（`startTaskWatch.ts`）  
- gate 改片时 bump watch key、清理 override（`ProjectWorkbench` / `MaterialReviewPanel`）

### 现象 B — slot-6 重试显示 slot-1 的 403

UI 展示「AI 视频生成失败」+ DashScope `AllocationQuota.FreeTierOnly`（`request_id: c591e62e-…`）。

### 根因 B

同 task `c041476f-…` 在 **7/2** 全量生成时 **slot-1** Pexels  miss → `video_generation` 403；**7/4** slot-6 重试真实错误为 `material_scaffold_failed`（`slot-6-stock-normalized.mp4` 未在 `generated/` 解析）。前端或用户若只看 `video_generation_failed` 文案会误判。

### 排障检查清单

1. `task_events` 按 `id DESC` 看 **最新** failed 事件的 `error.code`  
2. `generation-plan.json` 确认该 slot 的 `completionActions` 是否含 `video_generation`  
3. `material-state.json` 的 `videoGenQuota.used`  
4. 区分 **`video` provider（生视频）** vs **`videoUnderstanding`（素材审核 multimodal）**

---

## 5. 案例四：Gate 重试误走 Fork Revise

### 现象

素材 gate 内 slot-6 失败后点重试：`Revise generation is missing sourceGenerationId`。

### 根因

`pipeline_runner.retry_task` 见 `revise-context.json` 即调用 `start_revise()`；gate 原地改片只有 `materialGateRevise`，无 fork 所需 `sourceGenerationId`。

### 解决方案

- `is_fork_revise_context()` — 仅有 `materialGateRevise` 时返回 false  
- 非 fork → `start_generation(resume=True)`  
- resume 时从 `materialGateRevise.affectedSlotIds` 恢复 `slot_filter`（queue 已 consumed）

### 关键文件

- `services/shared/material_review_revise_context.py`  
- `services/api/app/services/pipeline_runner.py`  
- `services/worker/app/pipelines/material_slot_revise.py`  
- `services/worker/app/pipelines/p0_demo_pipeline.py`  

---

## 技术决策记录

| 决策 | 备选 | 选择 | 理由 |
|------|------|------|------|
| Session 后审片 | 继续 LLM finalize | **零 LLM gate finalize** | 降本、避免结论分裂、in-session marker 为 SSOT |
| 失败 session | 不出片 | **仍 materialize 最后一轮 preview** | 用户可看片后 NL 改片或 override |
| Gate NL 改片 in-session review | 默认开启 | **默认关闭**（env opt-in） | 改片已有人工 gate，避免重复 multimodal 配额 |
| packaging cta + HF-only reconcile | 保留 `source_then_polish` 双动作 | **单动作 `hf_native`** | 执行链仅 `[hyperframes_material]`，避免 plan/执行不一致 |

---

## 配置与运维备忘

| 变量 | 默认 | 说明 |
|------|------|------|
| `VIDEOMAKER_MATERIAL_REVIEW_ACP_IN_SESSION` | true | 首次生成 ACP in-session LLM 审片 |
| `VIDEOMAKER_MATERIAL_REVIEW_ACP_IN_SESSION_REVISE` | false | gate 内 NL 改片是否 in-session 审片 |
| `VIDEOMAKER_MATERIAL_REVIEW_ENABLED` | true | 总开关 |

**审核路由**（`resolve_material_review_route`）：配置了 `videoUnderstanding` 且 preview 在 size/duration 限制内 → `video` 路由（**非** `video_generation`）。

---

## 测试与验证

```powershell
cd services/worker
python -m pytest tests/test_material_gate_finalize.py tests/test_material_gate_promote.py `
  tests/test_revise_material_edit.py tests/test_material_slot_revise.py `
  tests/test_retry_task_routing.py tests/test_gap_reconcile.py `
  tests/test_acp_author.py -q

cd services/api
python -m pytest tests/test_retry_task_routing.py tests/test_material_review_routes.py -q

cd apps/web
npm run test -- features/tasks/ tests/task-event-merge.test.ts tests/taskMilestones.test.ts
```

**手工验证**：generation `5d5f3ec4` 全片生成成功；gate 内 slot-6 NL 改片 → retry → approve-material → 成片。

---

## 常见问题（Q&A）

### Q1：slot-6 是 HF-only，为什么报错像「视频模型配额」？

**A**：403 可能来自 (1) **同 task 历史** slot-1 的 `video_generation_failed` 被 UI 展示；(2) in-session **videoUnderstanding** 审核（与生视频不同 provider）。查最新 `task_events.error.code` 与 `completionActions`。

### Q2：finalize 还会调 LLM 吗？

**A**：不会。`finalize_slot_material_gate()` 禁止 `run_slot_review()`；只 materialize + promote marker。

### Q3：in-session review 失败还能进 gate 吗？

**A**：可以。finalize 仍 copy 最后一轮 preview；state 为 `agent_failed`，用户可 NL 改片或人工 override（见 plan § 人工批准策略）。

---

## 本会话关联改动（按模块）

| 模块 | 主要文件 |
|------|----------|
| contracts | `material-review-report/state` schema，`reviewPhase` / `finalSource` |
| shared | `material_review_revise_context.is_fork_revise_context`，`material_disk` approvable |
| worker gate | `material_gate_finalize.py`，`material_gate_promote.py` |
| worker revise | `revise_material_edit.normalize_*`，ACP payload，hyperframes provider |
| worker gap | `gap_reconcile` packaging HF-only |
| api | `pipeline_runner` retry 路由，generation failed 落盘 |
| web | `taskEventMerge`，`startTaskWatch`，`ProjectWorkbench` |

---

## 遗留风险与后续改进

1. **底片 staging**：gate revise edit 模式引用 `slot-N-stock-normalized.mp4` 时，需保证 `generated/` 与 scratch 同步，避免 `material_scaffold_failed`。  
2. **Stale 错误 UI**：失败 banner 应绑定最新 terminal event，勿展示历史 `video_generation_failed`。  
3. **slotId 写入 review report**：部分路径仍写 `slotId: "slot"` 而非 `slot-6`，影响按 slot 复用报告。  
4. **旧 generation plan**：reconcile 修复仅对新跑 gap/plan 生效；旧 artifact 的 `completionMode` 可能仍与执行链不一致。

---

*文档版本：2026-07-04 · 对应会话：material-gate-finalize · revise-context · task-progress*
