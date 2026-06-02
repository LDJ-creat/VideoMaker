# P1 Execution Order And Agent Prompts

本文档定义 P1 各专项计划的**依赖关系、执行波次、并行策略**，以及在新 Cursor 会话中交给 Agent 执行时**可直接复制粘贴的提示词**。

**Master plan:** [`2026-05-29-videomaker-p1-implementation-plan.md`](./2026-05-29-videomaker-p1-implementation-plan.md)

**前置条件：** P0 已合并到 `main`；每个专项使用独立 worktree + feature 分支；`.worktrees/` 已在 `.gitignore`。

---

## 1. 依赖关系图

```mermaid
flowchart TD
  C[contracts-extension]
  G[model-gateway]
  H[hyperframes-material]
  A[agent-orchestration]
  S[llm-structure-analysis]
  U[asset-understanding]
  M[semantic-mapping-gap]
  I[aigc-material-completion]
  HF[hyperframes-material provider merge]
  V[multi-variant-generation]
  R[nl-revise]
  W[web-workbench]
  O[observability]

  C --> G
  C --> H
  C --> W
  G --> A
  G --> I
  A --> S
  A --> U
  A --> M
  A --> R
  A --> O
  H --> HF
  I --> HF
  M --> V
  HF --> V
  V --> R
  V --> W
  R --> W
  O --> W
  G --> O
  A --> O
  V --> O
```

**说明：** `hyperframes-material` 模板与工具可在 Wave 2 与 `model-gateway` 并行；与 `aigc-material` 的 **completion_registry 注册**在 Wave 4 前合并协调。`observability` 的 **model-gateway status API** 应尽早合并，供 web Phase B Task 7 使用。

---

## 2. 执行波次（Waves）

### Wave 0 — 串行（必须先完成）

| 顺序 | 计划 | 分支 | 合并目标 |
| --- | --- | --- | --- |
| 1 | contracts-extension | `feature/p1-contracts-extension` | `main` |

**Gate：** `packages/contracts` 的 `npm run check` + `validate:schemas` 通过后再开 Wave 1 worktree。

---

### Wave 1 — 并行（contracts 已合并）

| 计划 | 分支 | 并行组 |
| --- | --- | --- |
| model-gateway | `feature/p1-model-gateway` | **A** |
| hyperframes-material（模板 + Tool，不含 registry 合并） | `feature/p1-hyperframes-material` | **A** |
| web-workbench（仅 contracts 类型 + fixture UI） | `feature/p1-web-workbench` | **B**（可选提前） |

**Gate：** model-gateway 合并后再开 Wave 2 的 agent-orchestration。

---

### Wave 2 — 串行 + 并行

| 顺序 | 计划 | 分支 | 说明 |
| --- | --- | --- | --- |
| 2a | agent-orchestration | `feature/p1-agent-orchestration` | **必须**在 gateway 之后 |
| 2b | llm-structure-analysis | `feature/p1-llm-structure-analysis` | 与 2c、2d 并行 |
| 2c | asset-understanding | `feature/p1-asset-understanding` | 与 2b、2d 并行 |
| 2d | semantic-mapping-gap | `feature/p1-semantic-mapping-gap` | 建议在 2c 之后或 rebase 含 2c |

**Gate：** 三条 intelligence 分支合并后，进入 Wave 3。

---

### Wave 3 — 并行（intelligence 已合并）

| 计划 | 分支 | 并行组 |
| --- | --- | --- |
| aigc-material-completion | `feature/p1-aigc-material` | **C** |
| hyperframes-material（provider 注册 + 与 registry 集成） | rebase/merge `feature/p1-hyperframes-material` | **C** |

**Gate：** 两个都合并；`completion_registry` 同时注册 AIGC + HF providers。

---

### Wave 4 — 串行

| 顺序 | 计划 | 分支 |
| --- | --- | --- |
| 4 | multi-variant-generation | `feature/p1-multi-variant-generation` |

**Gate：** API 返回 `generations[]`（多 taskId）；latest  reload 策略落地。

---

### Wave 5 — 分阶段（observability 前置 + web 两阶段）

| 子波 | 计划 | 分支 | 说明 |
| --- | --- | --- | --- |
| **5a** | observability（**至少 Task 4** model-gateway status） | `feature/p1-observability` | 可在 multi-variant 之后或与之并行开发；**status API 必须先于 web Phase B** |
| **5b** | nl-revise | `feature/p1-nl-revise` | 依赖 Wave 4 |
| **5c** | web-workbench **Phase A** 收尾 | `feature/p1-web-workbench` | evidence、variant picker、NL fixture；可与 5b 并行 |
| **5d** | web-workbench **Phase B** | 同上分支继续 | multi-task 进度、artifact 预览、gateway 状态面板；依赖 5a + Wave 4 + material |

**Gate 5d：** `GET /api/settings/model-gateway` 可用；multi-variant 响应为数组；worker 在 material 阶段推送 `artifactRefs`。

---

### Wave 6 — 收尾

| 计划 | 分支 |
| --- | --- |
| observability 完整（agent-runs + Langfuse 可选，若 5a 仅做了 status） | `feature/p1-observability` |
| integration/p1-demo-flow | `integration/p1-demo-flow` |

**integration 任务：** 端到端 demo、`docs/demos/p1-demo-checklist.md`、删除残留 P0 规则代码；验证 web Phase A+B 与双 task 进度。

---

## 3. 推荐合并顺序（线性）

```text
1.  feature/p1-contracts-extension
2.  feature/p1-model-gateway
3.  feature/p1-hyperframes-material        (可 step 2 并行开发，step 7 前 merge)
4.  feature/p1-agent-orchestration
5.  feature/p1-llm-structure-analysis
6.  feature/p1-asset-understanding
7.  feature/p1-semantic-mapping-gap
8.  feature/p1-aigc-material
9.  feature/p1-multi-variant-generation
10. feature/p1-observability          (至少 model-gateway status，供 web Phase B)
11. feature/p1-nl-revise
12. feature/p1-web-workbench         (Phase A 可提前；Phase B 在 10+9 之后)
13. feature/p1-observability         (补全 agent-runs / Langfuse，若 step 10 未做)
14. integration/p1-demo-flow
```

---

## 4. 并行开发规则

**禁止并行：**

- 未合并的 contracts schema 变更与其他分支同时改同一 schema 文件。
- 在 `agent-orchestration` 未合并时删除 `structure_pipeline.py` 的其他分支仍引用它。
- `TaskEvent.stage` 枚举变更不同步 `apps/web` 进度文案。

**安全并行：**

- Wave 1：`model-gateway` + `hyperframes-material` + `web` fixtures。
- Wave 2：`llm-structure` + `asset-understanding` + `semantic-mapping`（不同文件为主）。
- Wave 3：`aigc-material` + HF provider 集成（需沟通 `completion_registry.py`）。
- Wave 5b/5c：`nl-revise` + web Phase A。
- Wave 5d 前：确保 `observability` 的 model-gateway status 已合并。

**Web 两阶段：**

- **Phase A**（Wave 1 可启动）：fixture UI，不依赖 live multi-task API。
- **Phase B**（Wave 5d）：依赖 multi-variant + model-gateway status + material artifactRefs。

---

## 5. 新会话 Agent 提示词（复制粘贴）

> **顺序说明：** 本节编号与 **§6 快速参考表（执行日历）** 一致，而非历史线性 merge 编号。  
> 每个会话**只执行一条**提示词。并行 Wave 可同时开多个会话，但须 **各用独立 worktree**。  
> 标题格式：`Wave X — 专项名`。

---

### 5.1 · Wave 0 — Contracts Extension

```text
【Wave 0 · 串行 · P1 必须最先完成】

你是 VideoMaker 项目的 P1 contracts-extension 专项实现 Agent。

请先阅读：
- D:\VideoMaker\AGENTS.md
- D:\VideoMaker\docs\superpowers\specs\2026-05-27-videomaker-design.md
- D:\VideoMaker\docs\superpowers\plans\2026-05-29-videomaker-p1-implementation-plan.md
- D:\VideoMaker\docs\superpowers\plans\2026-05-29-p1-contracts-extension-plan.md
- D:\VideoMaker\docs\superpowers\plans\2026-05-29-p1-execution-order-and-prompts.md

你的任务：
1. 从 main 创建 worktree：D:\VideoMaker\.worktrees\p1-contracts，分支 feature/p1-contracts-extension。
2. 严格按 contracts-extension plan 使用 TDD 执行；这是 P1 Wave 0，必须最先完成。
3. 只修改 plan 允许的文件：packages/contracts/** 及 plan 中列出的 worker schema_loader 测试。
4. 不要修改 services/api、services/worker 业务逻辑、apps/web（除 schema_loader 测试期望）。
5. 新增 EditIntent、MaterialSpec、AgentRunLog schema；扩展 TaskEvent、AssetInventory、GapReport、RenderTimeline；添加 variants/registry.yaml。
6. 锁定决策：默认 enabled variants 为 high_click、high_conversion。

完成前必须运行：
cd D:\VideoMaker\.worktrees\p1-contracts\packages\contracts
npm run check
npm run validate:schemas

cd ..\..\services\worker
python -m pytest tests/test_schema_loader.py -v

全部通过后提交（仅当用户要求 commit 时）。完成后告知应合并到 main 再开始 Wave 1。
```

---

### 5.2 · Wave 1 — Model Gateway

```text
【Wave 1 · 可与 5.3、5.4 并行 · 须等 Wave 0 merge】

你是 VideoMaker 项目的 P1 model-gateway 专项实现 Agent。

请先阅读：
- D:\VideoMaker\AGENTS.md
- D:\VideoMaker\docs\superpowers\plans\2026-05-29-videomaker-p1-implementation-plan.md
- D:\VideoMaker\docs\superpowers\plans\2026-05-29-p1-model-gateway-plan.md
- D:\VideoMaker\docs\superpowers\plans\2026-05-29-p1-execution-order-and-prompts.md

前置：feature/p1-contracts-extension 已合并到 main。从最新 main 创建 worktree。

你的任务：
1. Worktree：D:\VideoMaker\.worktrees\p1-gateway，分支 feature/p1-model-gateway。
2. 实现 ModelGateway：OpenAI 兼容 text/vision/TTS/image + 可插拔 video submit/poll。
3. 禁止引入 LiteLLM。
4. 修改 llm_tool.py 接入 gateway；保留 fixture_mode 供 CI。
5. 只修改 plan 允许的文件：services/worker/app/gateway/**、llm_tool.py、相关 tests。

完成前必须运行：
cd D:\VideoMaker\.worktrees\p1-gateway\services\worker
python -m pytest tests/test_model_gateway.py tests/test_openai_compatible_providers.py tests/test_llm_tool.py -v
python -m compileall app

完成后 merge 到 main，再开 Wave 2a（5.5）。
```

---

### 5.3 · Wave 1 — HyperFrames Material（模板与 Tool）

```text
【Wave 1 · 可与 5.2、5.4 并行 · 本阶段不做 completion_registry 注册】

你是 VideoMaker 项目的 P1 hyperframes-material 专项实现 Agent（Wave 1 阶段）。

请先阅读：
- D:\VideoMaker\AGENTS.md
- D:\VideoMaker\docs\superpowers\plans\2026-05-29-p1-hyperframes-material-plan.md
- D:\VideoMaker\docs\superpowers\plans\2026-05-29-p1-execution-order-and-prompts.md

前置：feature/p1-contracts-extension 已合并。可与 model-gateway 并行开发。

你的任务（Wave 1 范围 only）：
1. Worktree：D:\VideoMaker\.worktrees\p1-hf-material，分支 feature/p1-hyperframes-material。
2. 实现 HyperFramesMaterialTool、benefit-card / title-lower-third / ken-burns 模板、MaterialAuthor Agent。
3. 不要在本阶段注册 completion_registry（留待 Wave 3 · 5.10）。
4. 只修改 plan 允许的文件。

完成前必须运行：
cd D:\VideoMaker\.worktrees\p1-hf-material\services\worker
python -m pytest tests/test_hyperframes_material_tool.py -v
python -m compileall app
```

---

### 5.4 · Wave 1 — Web Workbench Phase A（启动）

```text
【Wave 1 · 可与 5.2、5.3 并行 · 仅 fixture / 契约 UI，不接 live 多 task API】

你是 VideoMaker 项目的 P1 web-workbench 专项实现 Agent（Phase A · 启动）。

请先阅读：
- D:\VideoMaker\AGENTS.md
- D:\VideoMaker\docs\superpowers\plans\2026-05-29-p1-web-workbench-plan.md
- D:\VideoMaker\docs\superpowers\plans\2026-05-29-p1-execution-order-and-prompts.md

前置：feature/p1-contracts-extension 已合并。

你的任务（web-workbench plan Task 1–4 为主，可先不做 NL live）：
1. Worktree：D:\VideoMaker\.worktrees\p1-web，分支 feature/p1-web-workbench。
2. 扩展 apiClient + fixture-resolver（multi-variant / model-gateway / revise 的 fixture 形状）。
3. VariantPicker + VariantTabs（fixture）、StructureEvidencePanel、GeneratedAssetBadge 骨架。
4. 只修改 apps/web/**。

完成前必须运行：
cd D:\VideoMaker\.worktrees\p1-web\apps\web
npm run typecheck
npm run test
npm run build

说明：Phase A 收尾在 Wave 5c（5.14）；Phase B 在 Wave 5d（5.15）。
```

---

### 5.5 · Wave 2a — Agent Orchestration

```text
【Wave 2a · 串行 · 须等 Wave 1 的 model-gateway merge · 不可与 5.6–5.8 同时开工】

你是 VideoMaker 项目的 P1 agent-orchestration 专项实现 Agent。

请先阅读：
- D:\VideoMaker\AGENTS.md
- D:\VideoMaker\docs\superpowers\plans\2026-05-29-videomaker-p1-implementation-plan.md
- D:\VideoMaker\docs\superpowers\plans\2026-05-29-p1-agent-orchestration-plan.md
- D:\VideoMaker\docs\superpowers\plans\2026-05-29-p1-execution-order-and-prompts.md

前置：contracts-extension + model-gateway 已合并到 main。

你的任务：
1. Worktree：D:\VideoMaker\.worktrees\p1-agents，分支 feature/p1-agent-orchestration。
2. 实现 AgentRunner、PromptLoader、AgentRunStore。
3. 用 Agent + fixture 替换 structure_pipeline 及 generation 确定性语义逻辑。
4. 删除 structure_pipeline.py；LLM 失败不得回退规则模式。
5. 允许修改：services/worker/app/agents/**、pipelines/**、llm_tool fixtures、packages/prompts/agents/**、相关 tests。

完成前必须运行：
cd D:\VideoMaker\.worktrees\p1-agents\services\worker
python -m pytest -v
python -m compileall app

cd ..\..\services\api
python -m pytest -v

完成后 merge 到 main，再并行开 Wave 2b/c/d（5.6、5.7、5.8）。
```

---

### 5.6 · Wave 2b — LLM Structure Analysis

```text
【Wave 2b · 可与 5.7 并行 · 须等 5.5 merge · 建议先于或与 5.8 并行】

你是 VideoMaker 项目的 P1 llm-structure-analysis 专项实现 Agent。

请先阅读：
- D:\VideoMaker\AGENTS.md
- D:\VideoMaker\docs\superpowers\plans\2026-05-29-p1-llm-structure-analysis-plan.md
- D:\VideoMaker\docs\superpowers\plans\2026-05-29-p1-execution-order-and-prompts.md

前置：agent-orchestration 已合并。可与 asset-understanding、semantic-mapping-gap 并行。

你的任务：
1. Worktree：D:\VideoMaker\.worktrees\p1-structure，分支 feature/p1-llm-structure-analysis。
2. 实现 multimodal StructureAnalyst：structure_inputs.py、structure_validator.py、vision profile。
3. 强化 structure_analyst.md prompt 与 evidence 校验。
4. 只修改 plan 允许的文件范围。

完成前必须运行：
cd D:\VideoMaker\.worktrees\p1-structure\services\worker
python -m pytest tests/test_structure_inputs.py tests/test_structure_validator.py tests/test_structure_analyst_agent.py tests/test_p0_demo_pipeline.py -v
```

---

### 5.7 · Wave 2c — Asset Understanding

```text
【Wave 2c · 可与 5.6 并行 · 须等 5.5 merge · 5.8 建议在本分支 merge 后或 rebase 含本分支】

你是 VideoMaker 项目的 P1 asset-understanding 专项实现 Agent。

请先阅读：
- D:\VideoMaker\AGENTS.md
- D:\VideoMaker\docs\superpowers\plans\2026-05-29-p1-asset-understanding-plan.md
- D:\VideoMaker\docs\superpowers\plans\2026-05-29-p1-execution-order-and-prompts.md

前置：agent-orchestration 已合并。

你的任务：
1. Worktree：D:\VideoMaker\.worktrees\p1-assets，分支 feature/p1-asset-understanding。
2. 实现 ContentStrategist、asset_understanding.py、highlight 打分与 visualTags/suggestedSegmentRoles。
3. 接入 generation pipeline 的 analyzing_assets 阶段。
4. 只修改 plan 允许的文件。

完成前必须运行：
cd D:\VideoMaker\.worktrees\p1-assets\services\worker
python -m pytest tests/test_asset_understanding.py tests/test_generation_plan.py -v
```

---

### 5.8 · Wave 2d — Semantic Mapping And Gap Planning

```text
【Wave 2d · 建议 5.7 merge 后开工 · 可与 5.6 后期并行】

你是 VideoMaker 项目的 P1 semantic-mapping-gap 专项实现 Agent。

请先阅读：
- D:\VideoMaker\AGENTS.md
- D:\VideoMaker\docs\superpowers\plans\2026-05-29-p1-semantic-mapping-gap-plan.md
- D:\VideoMaker\docs\superpowers\plans\2026-05-29-p1-execution-order-and-prompts.md

前置：agent-orchestration 已合并；建议 rebase 含 asset-understanding。

你的任务：
1. Worktree：D:\VideoMaker\.worktrees\p1-gap，分支 feature/p1-semantic-mapping-gap。
2. 实现 SlotMapper、GapPlanner Agent 与 gap_selection.py 提供商选择算法（master plan §8.4）。
3. matchReason 必须为自然语言；VideoGenQuota 接口预留（quota=1）。
4. 只修改 plan 允许的文件。

完成前必须运行：
cd D:\VideoMaker\.worktrees\p1-gap\services\worker
python -m pytest tests/test_gap_selection.py tests/test_slot_mapper_agent.py tests/test_generation_plan.py -v

Wave 2 全部 merge 后进入 Wave 3（5.9、5.10）。
```

---

### 5.9 · Wave 3 — AIGC Material Completion

```text
【Wave 3 · 可与 5.10 并行 · 须等 Wave 2 全部 merge】

你是 VideoMaker 项目的 P1 aigc-material-completion 专项实现 Agent。

请先阅读：
- D:\VideoMaker\AGENTS.md
- D:\VideoMaker\docs\superpowers\plans\2026-05-29-p1-aigc-material-completion-plan.md
- D:\VideoMaker\docs\superpowers\plans\2026-05-29-p1-execution-order-and-prompts.md

前置：model-gateway + semantic-mapping-gap 已合并。

你的任务：
1. Worktree：D:\VideoMaker\.worktrees\p1-aigc，分支 feature/p1-aigc-material。
2. 实现 ImageGenTool、VideoGenTool、TTSTool、completion_registry、VideoGenQuota（每 generation 最多 1 次 video）。
3. 接入 generation_pipeline generating_material 阶段；失败不 fallback。
4. 只修改 plan 允许的文件。

完成前必须运行：
cd D:\VideoMaker\.worktrees\p1-aigc\services\worker
python -m pytest tests/test_image_gen_tool.py tests/test_video_gen_quota.py tests/test_completion_registry.py -v
```

---

### 5.10 · Wave 3 — HyperFrames Material（Provider 注册）

```text
【Wave 3 · 可与 5.9 并行 · 在同一 feature/p1-hyperframes-material 分支上 rebase 后继续 · 后 merge 方负责 completion_registry 集成】

你是 VideoMaker 项目的 P1 hyperframes-material 专项实现 Agent（Wave 3 阶段）。

请先阅读：
- D:\VideoMaker\AGENTS.md
- D:\VideoMaker\docs\superpowers\plans\2026-05-29-p1-hyperframes-material-plan.md
- D:\VideoMaker\docs\superpowers\plans\2026-05-29-p1-aigc-material-completion-plan.md
- D:\VideoMaker\docs\superpowers\plans\2026-05-29-p1-execution-order-and-prompts.md

前置：Wave 1 的 HF 模板已 merge；aigc-material 已 merge 或与之并行（合并时集成 registry）。

你的任务（Wave 3 范围 only）：
1. 在 feature/p1-hyperframes-material 分支 rebase 最新 main（含 aigc）。
2. 实现 hyperframes_material_provider；注册到 completion_registry（与 AIGC providers 共存）。
3. 跑全量 worker pytest 确认 registry 无冲突。

完成前必须运行：
cd D:\VideoMaker\.worktrees\p1-hf-material\services\worker
python -m pytest -v
python -m compileall app

Wave 3 全部 merge 后进入 Wave 4（5.11）。
```

---

### 5.11 · Wave 4 — Multi-Variant Generation

```text
【Wave 4 · 串行 · 须等 Wave 3 全部 merge】

你是 VideoMaker 项目的 P1 multi-variant-generation 专项实现 Agent。

请先阅读：
- D:\VideoMaker\AGENTS.md
- D:\VideoMaker\docs\superpowers\plans\2026-05-29-p1-multi-variant-generation-plan.md
- D:\VideoMaker\docs\superpowers\plans\2026-05-29-p1-web-workbench-plan.md  （Frontend Contract 章节）
- D:\VideoMaker\docs\superpowers\plans\2026-05-29-p1-execution-order-and-prompts.md

前置：semantic-mapping-gap + aigc-material + hyperframes-material 已合并。

你的任务：
1. Worktree：D:\VideoMaker\.worktrees\p1-variants，分支 feature/p1-multi-variant-generation。
2. POST generation-plan 返回 generations[]（每 variant 独立 generationId + taskId）；默认 high_click + high_conversion。
3. 实现 latest generation  reload（Option A 或 B，见 plan）供前端多 tab 恢复。
4. 每 generationId 独立 VideoGenQuota=1。
5. 修改 API + worker；更新 test_p0_flow_routes 期望。

完成前必须运行：
cd D:\VideoMaker\.worktrees\p1-variants\services\api
python -m pytest tests/test_multi_variant_generation.py tests/test_p0_flow_routes.py -v

cd ..\worker
python -m pytest tests/test_variant_overrides.py -v

完成后 merge，进入 Wave 5（5.12–5.15）。
```

---

### 5.12 · Wave 5a — Observability（Model Gateway Status API）

```text
【Wave 5a · 可与 5.13、5.14 并行开发 · status API 须在 5.15 之前 merge】

你是 VideoMaker 项目的 P1 observability 专项实现 Agent（Wave 5a · 仅 status API）。

请先阅读：
- D:\VideoMaker\AGENTS.md
- D:\VideoMaker\docs\superpowers\plans\2026-05-29-p1-observability-plan.md
- D:\VideoMaker\docs\superpowers\plans\2026-05-29-p1-web-workbench-plan.md
- D:\VideoMaker\docs\superpowers\plans\2026-05-29-p1-execution-order-and-prompts.md

前置：agent-orchestration + model-gateway 已合并；Wave 4 已 merge（推荐，非硬阻塞开发）。

你的任务（仅 observability plan Task 4）：
1. Worktree：D:\VideoMaker\.worktrees\p1-obs，分支 feature/p1-observability。
2. 实现 GET /api/settings/model-gateway + model_gateway_status.py；响应不得含 API Key。
3. 不要在本阶段实现 agent-runs / Langfuse（留待 Wave 6 · 5.16）。

完成前必须运行：
cd D:\VideoMaker\.worktrees\p1-obs\services\api
python -m pytest tests/test_model_gateway_status_route.py -v
```

---

### 5.13 · Wave 5b — Natural Language Revise

```text
【Wave 5b · 可与 5.12、5.14 并行 · 须等 Wave 4 merge】

你是 VideoMaker 项目的 P1 nl-revise 专项实现 Agent。

请先阅读：
- D:\VideoMaker\AGENTS.md
- D:\VideoMaker\docs\superpowers\plans\2026-05-29-p1-nl-revise-plan.md
- D:\VideoMaker\docs\superpowers\plans\2026-05-29-p1-execution-order-and-prompts.md

前置：multi-variant-generation 已合并。

你的任务：
1. Worktree：D:\VideoMaker\.worktrees\p1-revise，分支 feature/p1-nl-revise。
2. 实现 EditIntentParser、IntentApplier、revise_pipeline、POST /api/generations/{id}/revise。
3. 新 generationId，不覆盖源 generation；持久化 edit-intent.json。
4. 只修改 plan 允许的文件。

完成前必须运行：
cd D:\VideoMaker\.worktrees\p1-revise\services\api
python -m pytest tests/test_revise_generation.py -v

cd ..\worker
python -m pytest tests/test_intent_applier.py tests/test_revise_pipeline.py -v
```

---

### 5.14 · Wave 5c — Web Workbench Phase A（收尾）

```text
【Wave 5c · 可与 5.12、5.13 并行 · 同一 feature/p1-web-workbench 分支 · 在 5.15 之前完成】

你是 VideoMaker 项目的 P1 web-workbench 专项实现 Agent（Phase A · 收尾）。

请先阅读：
- D:\VideoMaker\AGENTS.md
- D:\VideoMaker\docs\superpowers\plans\2026-05-29-p1-web-workbench-plan.md
- D:\VideoMaker\docs\superpowers\plans\2026-05-29-p1-multi-variant-generation-plan.md
- D:\VideoMaker\docs\superpowers\plans\2026-05-29-p1-execution-order-and-prompts.md

前置：Wave 1 的 5.4 已做或跳过；contracts 已 merge。revise / multi-variant 的 fixture 形状已稳定。

你的任务（web-workbench plan Task 5–6）：
1. 继续在 D:\VideoMaker\.worktrees\p1-web，分支 feature/p1-web-workbench。
2. ReviseInputBar + EditIntentList（fixture）；补齐 VariantPicker/Tabs、StructureEvidence、AIGC badges。
3. 接入 ProjectWorkbench 布局；保持 P0 向后兼容。
4. 不要实现 Phase B（Task 7–13，见 5.15）。

完成前必须运行：
cd D:\VideoMaker\.worktrees\p1-web\apps\web
npm run typecheck
npm run test
npm run build
```

---

### 5.15 · Wave 5d — Web Workbench Phase B

```text
【Wave 5d · 串行收尾 · 须等 5.11、5.12 merge，建议 5.13 merge · 不可与 Phase A 混在同一会话】

你是 VideoMaker 项目的 P1 web-workbench 专项实现 Agent（Phase B · live 集成）。

请先阅读：
- D:\VideoMaker\AGENTS.md
- D:\VideoMaker\docs\superpowers\plans\2026-05-29-p1-web-workbench-plan.md
- D:\VideoMaker\docs\superpowers\plans\2026-05-29-p1-multi-variant-generation-plan.md
- D:\VideoMaker\docs\superpowers\plans\2026-05-29-p1-execution-order-and-prompts.md

Gate（全部满足后再开工）：
- GET /api/settings/model-gateway 可用（5.12 已 merge）
- POST generation-plan 返回 generations[]（5.11 已 merge）
- worker material 阶段推送 artifactRefs（Wave 3 已 merge）
- POST .../revise 可用（5.13 已 merge，若做 live NL 改片）

你的任务（web-workbench plan Task 7–13）：
1. 继续在 feature/p1-web-workbench，rebase 最新 main。
2. stageLabels、ModelGatewayStatusPanel、TaskArtifactPreview、useMultiTaskProgress、formatTaskError P1 码。
3. ProjectWorkbench：activeGenerations[] 多 task 进度；AgentRunsDrawer 可选。
4. 只修改 apps/web/**。

完成前必须运行：
cd D:\VideoMaker\.worktrees\p1-web\apps\web
npm run typecheck
npm run test
npm run build
```

---

### 5.16 · Wave 6 — Observability（Agent Runs 补全）

```text
【Wave 6 · 可与 integration 准备并行 · 须在 5.15 之后或与之无关的后端补全】

你是 VideoMaker 项目的 P1 observability 专项实现 Agent（Wave 6 · agent-runs 补全）。

请先阅读：
- D:\VideoMaker\AGENTS.md
- D:\VideoMaker\docs\superpowers\plans\2026-05-29-p1-observability-plan.md
- D:\VideoMaker\docs\superpowers\plans\2026-05-29-p1-execution-order-and-prompts.md

前置：Wave 5a（5.12）已 merge 到同一分支；agent-orchestration 已 merge。

你的任务（observability plan Task 1–3、5；Langfuse Task 4–5 可选）：
1. 继续在 feature/p1-observability，rebase main。
2. ObservabilitySink、GET /api/generations/{id}/agent-runs。
3. Langfuse 默认关闭。

完成前必须运行：
cd D:\VideoMaker\.worktrees\p1-obs\services\api
python -m pytest tests/test_model_gateway_status_route.py tests/test_agent_runs_route.py -v

cd ..\worker
python -m pytest tests/test_observability_sink.py -v
```

---

### 5.17 · Wave 6 — Integration P1 Demo Flow

```text
【Wave 6 · 串行收尾 · 须等 Wave 5 全部 merge（5.15 必做；5.16 可选）】

你是 VideoMaker 项目的 P1 integration 专项 Agent。

请先阅读：
- D:\VideoMaker\AGENTS.md
- D:\VideoMaker\docs\superpowers\plans\2026-05-29-videomaker-p1-implementation-plan.md
- D:\VideoMaker\docs\superpowers\plans\2026-05-29-p1-execution-order-and-prompts.md
- D:\VideoMaker\docs\demos\p0-demo-checklist.md

前置：Wave 1–5 全部专项已合并到 main（observability 可选）。

你的任务：
1. Worktree：D:\VideoMaker\.worktrees\p1-integration，分支 integration/p1-demo-flow。
2. 端到端验证：样例 LLM 结构 → 双 variant 生成 → NL revise → 渲染；修复集成缝隙。
3. 新增 docs/demos/p1-demo-checklist.md（按 master plan §17）。
4. 清理残留 P0 规则代码与死测试 import。
5. 运行全模块验证矩阵（contracts、api、worker、web）。

不要添加新功能；仅集成与修复。
```

---

## 6. 快速参考表（执行日历）

| Wave | §5 提示词 | 计划文件 | 分支 | 可并行 |
| --- | --- | --- | --- | --- |
| 0 | **5.1** | p1-contracts-extension-plan.md | feature/p1-contracts-extension | — |
| 1 | **5.2** | p1-model-gateway-plan.md | feature/p1-model-gateway | 5.3, 5.4 |
| 1 | **5.3** | p1-hyperframes-material-plan.md（模板） | feature/p1-hyperframes-material | 5.2, 5.4 |
| 1 | **5.4** | p1-web-workbench-plan.md（Phase A 启动） | feature/p1-web-workbench | 5.2, 5.3 |
| 2a | **5.5** | p1-agent-orchestration-plan.md | feature/p1-agent-orchestration | — |
| 2b | **5.6** | p1-llm-structure-analysis-plan.md | feature/p1-llm-structure-analysis | 5.7 |
| 2c | **5.7** | p1-asset-understanding-plan.md | feature/p1-asset-understanding | 5.6 |
| 2d | **5.8** | p1-semantic-mapping-gap-plan.md | feature/p1-semantic-mapping-gap | 5.6（5.7 后更佳） |
| 3 | **5.9** | p1-aigc-material-completion-plan.md | feature/p1-aigc-material | 5.10 |
| 3 | **5.10** | p1-hyperframes-material-plan.md（registry） | feature/p1-hyperframes-material | 5.9 |
| 4 | **5.11** | p1-multi-variant-generation-plan.md | feature/p1-multi-variant-generation | — |
| 5a | **5.12** | p1-observability-plan.md（status API） | feature/p1-observability | 5.13, 5.14 |
| 5b | **5.13** | p1-nl-revise-plan.md | feature/p1-nl-revise | 5.12, 5.14 |
| 5c | **5.14** | p1-web-workbench-plan.md（Phase A 收尾） | feature/p1-web-workbench | 5.12, 5.13 |
| 5d | **5.15** | p1-web-workbench-plan.md（Phase B） | feature/p1-web-workbench | — |
| 6 | **5.16** | p1-observability-plan.md（agent-runs） | feature/p1-observability | 5.17 准备 |
| 6 | **5.17** | integration/p1-demo-flow | integration/p1-demo-flow | — |

---

## 7. 会话执行建议

1. **按 §6 表格从上到下推进**；复制提示词时用 **§5 编号**（5.1–5.17），不要跳号。
2. **一次一会话一条提示词** — 避免 scope 膨胀。
3. **并行 Wave**（如 5.2∥5.3∥5.4）：每个会话独立 worktree，merge 后再开下一 Wave。
4. **completion_registry 冲突** — aigc（5.9）与 HF registry（5.10）合并时，后 merge 方负责集成两个 provider 并跑全量 worker pytest。
5. **用户未要求不要 commit** — 完成验证后可提交，便于 PR。
