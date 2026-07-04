# VideoMaker 会话复盘：生成取消/重试、Worker 卡死与进度 UI 一致性

> **会话背景**：在真实 generation 任务（`47bf4406-…` / task `7b14cd96-…`）上联调「取消 → 重试 → 并行 slot 补全 → 最终 MP4」全链路；并复盘同一 generation 中 **slot 3–6 HF 分镜贴底** 的布局问题及链路优化。  
> **文档用途**：项目复盘、新人 onboarding、面试中讲述「问题发现 → 根因 → 方案 → 验证」的完整案例。

---

## 1. 问题总览（按严重程度）

| # | 现象 | 根因类别 | 最终状态 |
|---|------|----------|----------|
| 1 | 取消后重试报 `Task cannot be retried from status 'cancelled'` | API 策略过严 | 已修复 |
| 2 | 取消后重试，双 worker 同时写同一 generation，任务挂死 20+ 分钟 | 进程生命周期 | 已修复 |
| 3 | slot MP4 已全部落盘，UI 仍显示 slot 1–4「补全中」 | 进度语义与数据源 | 已修复 |
| 4 | 进度条与迁移表矛盾（上方「并行 1–4」，下方全「已规划」） | 前端双状态源 | 已修复 |
| 5 | `material-state.json` 的 `completedActionIds` 长期为 `[]` | Worker 持久化/竞态（卡死加剧） | 部分缓解 + 磁盘推断兜底 |
| 6 | 取消 → 重试后 UI 滞后，需手动刷新页面 | 重试未重置派生状态 | 已修复 |
| 7 | slot 3–6 纯 HF 分镜主画面堆在底部而非居中 | `finishIntent` / ACP 贴底习惯 vs `hf_native` 语义 | 已优化（`layoutAnchor` + 按 mode 纠偏） |

---

## 2. 案例一：取消后无法重试

### 现象

工作台点击「取消」后点「重试」，API 返回 400：`Task cannot be retried from status 'cancelled'`。

### 根因

`retry_task` 仅允许 `failed` / `running`（且 running 时还要求「非 active」），未把 `cancelled` 视为可恢复终端态。  
而产品设计是：**同一 taskId + checkpoint 续跑**，取消不应等于「任务作废」。

### 解决方案

- `services/api/app/services/pipeline_runner.py`：`retry_task` 允许 `status=cancelled`。
- 与 `failed` 一样走「读 checkpoint → 重新 dispatch worker」路径。
- 单测：`services/api/tests/test_task_routes.py::test_retry_cancelled_task`。

### 面试可答要点

> 长任务系统要把 **cancelled** 和 **failed** 区分开语义，但若支持 checkpoint resume，cancelled 应允许 retry，且必须 **终止旧 worker**，否则会话二的问题。

---

## 3. 案例二：取消/重试后 Worker 卡死（最严重）

### 现象（真实数据）

- `generated/action-slot-1..5.mp4` 已写入；**slot-6 无任何产物**。
- checkpoint 停在 `planning_completion`，**没有** `generating_material`。
- `material-state.json`：`completedActionIds: []`。
- 取消后重试时 **两个 `run_p0_task.py` 进程**同时操作同一 generation。
- SSE 最后一条：`HyperFrames material ready for slot slot-5`，之后 20+ 分钟无事件。

### 根因（多层叠加）

1. **取消只改 SQLite，不杀子进程（主因）**  
   `POST /cancel` 仅 emit `status=cancelled`，`subprocess.run` 启动的 worker 仍在跑。

2. **重试再起 worker → 双进程竞争（主因）**  
   同一 `generationId` 目录被两个进程写，`material-state` / checkpoint 不一致。

3. **`ThreadPoolExecutor` + `future.result()` 无限等待（主因）**  
   并行 slot 中一个 ACP/HF 调用挂死，线程池线程永不返回，整批素材阶段卡住。

4. **`VIDEOMAKER_MATERIAL_MAX_CONCURRENT_SLOTS=3`（放大器）**  
   提高 ACP/FFmpeg 资源争用，但不是唯一原因。

### 解决方案

| 层级 | 改动 |
|------|------|
| API | `WorkerProcessRegistry`：按 `taskId` 注册 `Popen`；cancel/retry 时 Windows `taskkill /F /T` |
| API | `SubprocessDemoPipeline._invoke` 改为 `Popen` + `communicate`，可中断 |
| Worker | `material_parallel.py`：`wait(FIRST_COMPLETED)` + `VIDEOMAKER_MATERIAL_SLOT_TIMEOUT_SEC`，超时 `material_slot_timeout` + `request_cancel` |
| 配置 | `.env.example` 注明 cancel 杀进程；ACP 场景建议 `MAX_CONCURRENT_SLOTS=1` |

### 关键文件

- `services/api/app/services/worker_process_registry.py`
- `services/api/app/services/pipeline_runner.py`
- `services/worker/app/providers/material_parallel.py`

### 面试可答要点

> 分布式/长任务里 **取消 = 状态机 + 进程生命周期** 两件事。只更新 DB 不杀子进程，等于「逻辑取消、物理仍跑」。重试必须 **idempotent + 单写者**，否则 checkpoint 与产物目录都会坏。

---

## 4. 案例三：磁盘已有 MP4，UI 仍显示「补全中」

### 现象

`generated/` 下 6 个 slot 的 `action-slot-*.mp4` 均已存在，工作台迁移表 slot 1–4 仍为「补全中」，仅 slot 5–6「已补全」。

### 根因

前端 **完成态** 依赖三条互不一致的数据源：

1. **SSE 文案**：`Completing slot X` → 标记 active；仅 `HyperFrames material ready for slot X` → 标记 completed。  
   Stock / 非 HF 路径没有 ready 事件 → **永远留在 active**。
2. **`material-state.json`**：`completedActionIds` 为空（卡死时未持久化）→ `deriveCompletedSlotIds` 无效。
3. **未读磁盘**：UI 不知道 `action-slot-2.mp4` 已就绪。

slot 5–6 显示已补全，是因为历史 SSE 里恰好有 HF ready 事件。

### 解决方案

1. **Shared + API**：`services/shared/material_disk.py` 的 `infer_completed_slot_ids()`，与 worker 的 `expected_output_path` / 体积阈值对齐。  
   `GET /api/generations/{id}/migration-snapshot` 增加 `completedSlotIds`。
2. **Web**：`mergeCompletedMaterialSlotIds` 合并磁盘 + SSE + material-state；`reconcileMaterialSlotProgress` 从 active 中剔除已完成 slot。
3. **阶段门控**：`shouldInferDiskCompletedSlots()` — 仅在 `progressGroup ∈ {completing, done}` 使用磁盘推断，避免在 `mapping` 阶段误显示「全部已补全」。

### 面试可答要点

> UI 进度不能单信 SSE 文案。要有 **权威事实源**（磁盘 / DB / contract artifact），并对 **事件语义** 做归一化（不同 provider 的「完成」信号不同）。

---

## 5. 案例四：进度 UI 上下矛盾

### 现象

`TaskProgressPanel` 显示「并行处理 slot 1–4」；下方 `GenerationMigrationProgressPanel` 迁移表全是「已规划补全」。主消息行仍是英文 `HyperFrames material ready…`。

### 根因

1. **两个组件各调一次 `useParallelMaterialActivity`** → 状态不同步。
2. **`parseTaskMaterialProgress`** 把 HF ready 当成「正在处理」。
3. **`activeSlotIds` 驱动表格**，`completedActionIds` 为空时无法标「已补全」。

### 解决方案

- **单一状态源**：仅在 `TaskProgressPanel` 调 hook，经 `materialActivity` prop 下传。
- **`buildUnifiedMaterialProgressSummary`** 统一主/副文案；`formatTaskMessage` 翻译 HF/Completing 英文。
- **`reduceParallelMaterialActivity`**：HF ready → `completedSlots`，并从 `activeSlots` 移除。

### 面试可答要点

> 复杂进度 UI 要 **lift state up**；衍生状态（并行 slot 集合）应用 reducer 纯函数 + 单一订阅 SSE。

---

## 6. 案例五：取消 → 重试后 UI 明显滞后（需手动刷新）

### 现象

重试后主进度已是 5%「分析素材 / Resuming from checkpoint」，但顶部仍显示「已完成 slot-1…6、__master__」，迁移卡片停在「匹配中」，刷新页面才正常。

### 根因

重试 **复用同一 `taskId`**，但前端未按「新一次运行」重置：

| 模块 | 问题 |
|------|------|
| `useParallelMaterialActivity` | `resetKey` 未变时 **回放整段 SSE 历史**，旧 run 的 Completing/HF ready 再次生效 |
| `useGenerationMigrationArtifacts` | cancel 只 `invalidateCache`，**组件内 artifacts 未清空** |
| 磁盘 `completedSlotIds` | 在 `mapping` 阶段仍合并，显示上一轮全部完成 |
| `useTaskProgress` / `useMultiTaskProgress` | `watchKey` bump 后未清空 `event` / `lastEventId` |

### 解决方案

- 引入 **`progressResetKey`**（= `taskWatchKeys[taskId]`），cancel/retry 时 `bumpTaskWatchKey`。
- `useParallelMaterialActivity({ resetKey })`：retry 时 **清空且不回放历史**，仅跟 live SSE。
- `useGenerationMigrationArtifacts({ resetKey })`：retry/terminal 时 `setArtifacts(null)` 并强刷。
- `useTaskProgress`：`watchKey` 变化时 `event=null`、`lastEventId=0`。
- `useMultiTaskProgress`：watchKey 变化时删除该 task 的 cached event。

### 面试可答要点

> Retry 不是新 taskId 时，前端要把 **watchKey / generationAttempt** 当作逻辑代数。任何从 event log 衍生的状态，在 retry 时必须 **截断历史或按 attempt 过滤**。

---

## 7. 案例六：纯 HF 分镜贴底（slot 3–6 布局）

### 现象

对 generation `47bf4406-f5f1-4860-ba9f-e8abe662262f`（project `7bed327a-…`，variant `high_conversion`）复盘分镜时发现：**slot 3–6** 的 HF 成片主信息区贴在画面底部，竖屏中心区域空洞；slot 2 因 `authorPrompt` 写了「居中排版」而正常居中。

成片 CSS 证据（例：slot-3）：

- `.overlay-stack { justify-content: flex-end; }` + `.lower-band`
- slot-4：`.benefit-zone { bottom: 12%; }`
- slot-5：`.overlay-stage { align-items: flex-end; }`
- slot-6：`.cta-overlay { bottom: 0; }` + `.lower-third`（CTA 贴底在此 case 尚可理解，但与 timeline 字幕仍有叠层风险）

### 根因（多层）

1. **`storyboard_writer` 的 `authorPrompt` 未要求贴底**  
   slot-4 甚至写了「首行文案居中」；全局 `visualStyleBible.cameraGrammar` 的「人物居中」针对口播镜头，不约束全屏 HF 字卡。

2. **`gap_planner` / variant `finishIntentByRole` 引入贴底语义**  
   `high_conversion` 默认：`benefit_card` →「强化卖点字卡与**对比条**」；`cta` →「**lower third**」。「对比条 / lower third」在短视频语义里≈画面下三分之一。

3. **知识库样例迁移偏差**  
   参考 skill 含「底部大白字字幕」「账号信息 / logo 在底部」，ACP 易把 HF 全屏字卡也做成贴底。

4. **ACP material author 默认审美**  
   benefit_card / proof 类 slot 常产出 `flex-end` / `bottom` 锚定布局，与 `hf_native`（无主视频底片）不匹配。

5. **架构性叠层风险**  
   口播字幕由 **timeline 字幕轨** 统一烧录（9:16 默认 `bottomPaddingPx: 120`）；HF 内再在底部放可读文案，易与字幕轨重叠。`material_author` 规范本要求 HF 不重复口播，但 CTA 卡片仍可能底部叠字。

### 设计原则（本次优化）

按 **补全方式（mode）** 区分布局，**不区分画幅**（9:16 / 16:9 / 1:1 共用同一套 `layoutAnchor` 规则；刻意不做 per-aspect-ratio 分支，保持普适性）：

| `compositionAuthorBrief.mode` | `layoutAnchor` | 布局含义 |
|------------------------------|----------------|----------|
| `hf_native` / `packaging_only` | **`center`** | 纯 HF 全屏合成；主信息垂直水平居中；禁止贴底 lower third / flex-end |
| `source_then_polish` + CTA | `lower_third` | 保留 B-roll 人物；行动条在下方 1/3 细 overlay |
| `source_then_polish` + hook | `upper_third` | hook / 标题在上方 1/3 |
| `source_then_polish`（其他） | `lower_third` | 润色 overlay 贴底，不替换底片 |

**合理例外**：真实人物 B-roll 上 `source_then_polish` 的 CTA lower third **可以**贴底；**不合理**：`hf_native` 全屏金句/字卡（slot 3–5）或 `hf_native` CTA 仍贴底并与字幕轨抢位置。

### 解决方案

| 层级 | 改动 |
|------|------|
| **Contracts** | `compositionAuthorBrief.layoutAnchor`: `center` \| `lower_third` \| `upper_third` |
| **Worker** | `composition_brief.py`：按 `mode` 推断/强制 `layoutAnchor`；`hf_native` 的 `authorPrompt` 补居中提示 |
| **Worker** | `gap_reconcile.py` + `gap_planner.py`：`coerce_finish_intent_for_mode()` — `hf_native` 下「对比条 / lower third」改写为居中字卡意图 |
| **Worker** | `finish_brief.py`：向 material author 下发 `layoutDirective`（展开 CSS 纪律） |
| **Variants** | `registry.yaml`：`high_conversion.benefit_card` finishIntent 改为「竖屏居中卖点字卡…」 |
| **Prompts / Skills** | `storyboard_writer`、`gap_planner`、`material_author`；`videomaker-composition` / `SLOT-VISUAL-CRAFT` |
| **Composition** | `payload.py` 透传 `layoutDirective`；`forbidden_copy_guard` 补充 field semantics |

### 关键文件

- `packages/contracts/schemas/composition-author-brief.schema.json`
- `services/worker/app/pipelines/composition_brief.py`
- `services/worker/app/pipelines/gap_reconcile.py`
- `services/worker/app/agents/gap_planner.py`
- `services/worker/app/providers/finish_brief.py`
- `packages/contracts/variants/registry.yaml`
- `packages/prompts/agents/storyboard_writer.md`、`gap_planner.md`、`material_author.md`

### 验证

```powershell
cd services/worker
python -m pytest tests/test_composition_brief.py tests/test_finish_intent_layout.py -q

cd packages/contracts
npm run check
npm run validate:schemas
```

**预期**：新 generation 的 ACP payload 含 `compositionAuthorBrief.layoutAnchor: "center"`（`hf_native` slot）及对应 `layoutDirective`；成片 HTML 不再以 `flex-end` / `bottom` 锚定主文案。

### 面试可答要点

> 包装动效要区分 **「全屏生成」** 和 **「底片润色」** 两种物理模型。lower third 是 broadcast 里「人不挡、条在底」的 overlay 范式，不能套到无底片的 HF 字卡上。结构化字段（`layoutAnchor`）比 prompt 里写「排版对齐」更可靠；Python reconcile 还要把 variant 里「对比条」类 finishIntent 从 hf_native 路径上纠偏。

---

## 8. 架构与数据流（修复后）

```text
用户取消/重试
    │
    ▼
API: terminate worker (taskkill) + retry dispatch
    │
    ▼
Worker: checkpoint resume → generating_material (并行 slot + 超时)
    │                      → building_timeline → FFmpeg render → output.mp4
    ▼
SSE / GET task ──► useTaskProgress (watchKey 重置)
    │
    ├─► useParallelMaterialActivity (resetKey, 不回放历史)
    │
    └─► useGenerationMigrationArtifacts (resetKey, 强刷 snapshot)
              │
              └─► completedSlotIds (磁盘) + progressGroup 门控
                        │
                        ▼
              TaskProgressPanel + GenerationMigrationProgressPanel（单一 materialActivity）
```

---

## 9. 配置与运维备忘

| 变量 | 建议 | 说明 |
|------|------|------|
| `VIDEOMAKER_MATERIAL_MAX_CONCURRENT_SLOTS` | ACP 生产用 `1` | 降低 HF/ACP 争用 |
| `VIDEOMAKER_MATERIAL_SLOT_TIMEOUT_SEC` | 默认 2400 | 单 slot 链超时，总等待 ≈ timeout × slot 数 |
| `VIDEOMAKER_COMPOSITION_AUTHOR_BACKEND` | `acp` | 外部 agent 写 HF spec |
| Cancel | — | 会杀 worker 子进程（Windows taskkill） |

**排障检查清单**：

1. 任务卡住时：`tasklist | findstr python` 是否多个 worker 同 generation？
2. `generations/{id}/checkpoint.json` 的 `completedStages` 停在哪一 stage？
3. `material-state.json` 的 `completedActionIds` 是否更新？
4. `generated/action-slot-*.mp4` 是否存在且体积 > 15KB（HF 阈值）？
5. 前端是否 bump 了 `taskWatchKeys`（Network 里 SSE 是否从新事件开始）？

---

## 10. 测试与验证命令

```powershell
# API
cd services/api
python -m pytest tests/test_task_routes.py tests/test_worker_process_registry.py tests/test_generation_migration_snapshot.py -q

# Worker
cd services/worker
python -m pytest tests/test_material_parallel.py tests/test_acp_author.py tests/test_composition_brief.py tests/test_finish_intent_layout.py -q

# Contracts（含 composition-author-brief.layoutAnchor）
cd packages/contracts
npm run check
npm run validate:schemas

# Shared
cd services/shared
python -m pytest tests/test_material_disk.py -q

# Web
cd apps/web
npm run test -- lib/parallelMaterialActivity.test.ts features/tasks/TaskProgressPanel.test.tsx features/tasks/useTaskProgress.test.ts
```

**手工 E2E**：生成进行中 → 取消 → 确认 worker 进程消失 → 重试 → **不刷新页面** 观察进度与迁移表是否与 stage 一致 → 等待 `renders/.../output.mp4`。  
**HF 布局 E2E**：`hf_native` slot（如 benefit_card / proof）检查 ACP payload 含 `layoutAnchor: center`；成片 `composition/index.html` 主文案区非 `flex-end` / `bottom` 锚定。

---

## 11. 面试高频问答（Q&A）

### Q1：你们怎么定位「任务卡死但文件已生成」？

**A**：对比三层事实——SQLite task/SSE 最后事件、checkpoint `completedStages`、`generated/` 与 `material-state.json`。本次是 SSE 停在 slot-5 ready、checkpoint 未进 `generating_material`、双 worker + 线程池无限等待。定位后先杀进程再谈重试。

### Q2：为什么取消必须杀子进程？

**A**：Worker 是 API 拉起的独立 Python 进程，有自己的内存与线程池。仅把 DB 标为 cancelled 不会中断正在跑的 ACP session 或 `future.result()`。不杀进程重试会产生 **双写者**，比单进程卡死更难恢复。

### Q3：前端进度为什么不用 SSE 一条链路就够了？

**A**：SSE 是 **叙事日志**（人类可读 message），不是结构化状态机。不同 provider 完成信号不统一（HF 有 ready，stock 没有）。需要 snapshot API + 磁盘推断 + 按 stage 门控，才能把「展示进度」和「真实产物」对齐。

### Q4：retry 同 taskId 时前端要注意什么？

**A**：所有从 event history 衍生的 state（并行 slot map、迁移 artifact）必须在 `watchKey/resetKey` 变化时清空；SSE 订阅重置 `after_id`；避免重放取消前的历史 message。

### Q5：并行 slot 补全如何兼顾吞吐与稳定？

**A**：`ThreadPoolExecutor` 按 slot 链并行，但要有 **per-slot 超时** 和 **cancel 传播**；ACP 场景降低并发度。失败要快（fail_fast + request_cancel），不要无限等一个 slot。

### Q6：如果让你再做一版，会改架构哪一块？

**A**：（诚实加分项）  
- 给每次 retry 增加 **`runAttempt`** 写入 task event 与 material-state，前端只消费 `attempt` 匹配的事件；  
- Worker 侧用 **进程组 / job lease**（单 generation 互斥锁）；  
- 素材完成态以 **`material-state.json` 为准** 并修复并行下的持久化竞态，磁盘推断仅作 resume 辅助。

### Q7：HF 分镜为什么有时全贴底？你们怎么修？

**A**：把 **hf_native（纯生成）** 和 **source_then_polish（底片润色）** 当成两种物理模型。前者主信息必须 **center**，避免与 timeline 底部字幕重叠；后者 CTA/hook 才用 lower/upper third overlay。仅靠 prompt 不够，需要 **`layoutAnchor` + Python 对 finishIntent 纠偏**（如把 hf_native 上的「对比条」改成居中字卡）。画幅上刻意 **不** 做 9:16/16:9 分支，规则普适。

---

## 12. 本会话关联提交（main 上 7 commits）

| Commit | 范围 |
|--------|------|
| `ca8996d` | shared: `material_disk` 磁盘槽位推断 |
| `80304ff` | api: worker 注册表、cancel 杀进程、migration-snapshot |
| `3265a50` | worker: 并行素材超时 |
| `e2ce422` | worker: ACP turn loop / scratch / 可观测性 |
| `d027878` | composition: spec 归一化、MCP lint |
| `bd4bc89` | web: 取消重试、进度 reset、并行 UI |
| `f2369e6` | docs: ACP E2E 清单 |

**同会话后续（HF 布局，`layoutAnchor`，待提交）**：contracts / worker / composition prompts & skills — 见 §7。

---

## 13. 遗留风险与后续改进

1. **`material-state.json` 在并行+异常退出时仍可能为空** — 磁盘推断已兜底 UI，但 worker 应保证每个 slot 链结束后再批量 persist，或 retry 时从磁盘 backfill `completedActionIds`。
2. **`building_timeline` 在 pipeline 中接近 no-op** — 时间线主要在 plan/material 阶段写入，面试时可说明「阶段名与实现略有漂移」。
3. **双 variant 并行 generation** — 与单 task 内 slot 并行叠加时，仍需关注 API `MAX_CONCURRENT_GENERATIONS` 与机器资源。
4. **HF 布局优化待新 generation 回归** — §7 改动需在真实 ACP 路径上复跑 slot 3–6，确认 `layoutDirective` 被 Cursor 遵守；legacy `benefit-card` scaffold 仍含 `bottom: 120px`，仅影响 fallback 模板路径。

---

*文档版本：2026-06-23 · 对应会话：生成取消/重试、Worker 卡死、进度 UI 一致性、HF 纯生成布局（layoutAnchor）*
