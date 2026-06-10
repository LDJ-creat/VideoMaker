# VideoMaker — 爆款结构迁移引擎

> 从优质样例拆解创作结构，识别素材缺口，迁移到新主题与素材，生成可解释的分镜、时间线与成片 demo。

本项目为剪映 AI 创作竞赛课题实现：**不复制样例内容，而是迁移「创作方法」**——脚本段落、镜头节奏、包装样式等可复用结构，并在素材不足时通过补全策略完成成片。

本文档面向**首次了解项目的读者**（含评审）：优先用中文说明业务能力；代码标识、契约名与 API 路径在需要精确引用时保留英文。更完整的开发上下文、模块状态与 API 索引见 `[AGENTS.md](./AGENTS.md)`；架构规格见 `[docs/superpowers/specs/2026-05-27-videomaker-design.md](./docs/superpowers/specs/2026-05-27-videomaker-design.md)`。

---

## 目录

- [项目主题与目标](#项目主题与目标)
- [整体架构](#整体架构)
- [技术选型](#技术选型)
- [核心功能与亮点](#核心功能与亮点)
- [整体 AI 架构](#整体-ai-架构)
- [工具协议](#工具协议)
- [安全边界](#安全边界)
- [快速开始](#快速开始)
  - [模型配置](#模型配置)
- [数据存储说明](#数据存储说明)
- [仓库结构](#仓库结构)
- [验证与演示](#验证与演示)

---

## 项目主题与目标

**课题名称**：爆款结构迁移引擎 — 从样例拆解、素材补全到视频重组的 AI 创作平台。

系统打通的核心闭环：

```text
样例视频输入（支持批量上传 / 引用历史结构知识）
  → 算法感知：提取镜头、语音、关键帧等客观事实（FFmpeg / OpenCV / Whisper 等）
  → AI 结构分析：归纳可复用的创作结构（脚本、节奏、镜头槽位、证据链）
  → 新创作意图 + 用户素材理解：解析 Brief 与图片 / 视频 / 文案素材
  → 结构迁移：将样例槽位与用户素材语义匹配，识别「缺什么、怎么补」
  → 分镜与包装：生成全片口播稿、分镜脚本与字幕 / 贴纸等包装方案
  → 人工审阅（可关闭）：全片口播与分镜阶段可暂停，支持在线改稿
  → 素材补全：优先复用用户素材与图库检索，必要时用 HyperFrames 特效片段或 AIGC 补位；全片口播统一合成后再对齐字幕与时间线
  → 时间线合成 → FFmpeg 或 HyperFrames 输出成片 MP4
  → 可选：自然语言改片、双版本对比（高点击 / 高转化）、结构技能与包装模式入库
```

与竞赛评分维度的对应关系：结构定义清晰（四轨结构模型 + 分析证据）、迁移过程可解释（工作台全程可视化）、素材缺口可识别（缺口报告）、过程可见（实时任务进度与 AI 调用日志）、结果可验证（分镜稿 / 时间线 / 成片）。

---

## 整体架构

采用**前后端分离 + 契约驱动**的单仓多模块布局：

```text
┌─────────────────────────────────────────────────────────────────┐
│  apps/web          Next.js 工作台（浏览器 UI，代理 /api → 后端）   │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP + 服务端推送（任务进度事件）
┌────────────────────────────▼────────────────────────────────────┐
│  services/api      FastAPI：项目 / 样例 / 生成 / 知识库 / 设置 API │
│                    SQLite 存任务元数据；PipelineRunner 调度 Worker │
└────────────────────────────┬────────────────────────────────────┘
                             │ 子进程调用（同一任务 ID，支持断点续跑）
┌────────────────────────────▼────────────────────────────────────┐
│  services/worker   视频感知、AI 编排、素材补全、成片渲染            │
│  services/composition  HyperFrames 包装片段创作引擎               │
│  services/shared     API 与 Worker 共用的 Python 共享库           │
│                      （模型网关配置、路径安全校验、知识库索引、     │
│                       图库凭证、语音合成偏好等）                  │
└────────────────────────────┬────────────────────────────────────┘
                             │ 读写运行时产物
┌────────────────────────────▼────────────────────────────────────┐
│  services/api/storage/  项目产物、全球知识库、全局配置与日志     │
│  packages/contracts      跨模块 JSON 契约（TypeScript + Schema）  │
│  packages/prompts        AI 智能体 Prompt 模板                    │
└─────────────────────────────────────────────────────────────────┘
```

**任务与状态权威来源**：SQLite 任务表 + 进度事件流；前端以 SSE 实时推送为主、轮询为兜底。长任务支持 **断点续跑**（各阶段 checkpoint 写入项目存储目录），重试接口 `POST /api/tasks/{task_id}/retry` 会沿用同一任务 ID 从断点继续，而非新建任务。

**运行时存储路径（重要）**：产物目录 = **启动 API 时的当前工作目录** + `storage/`。按下方「快速开始」从 `services/api` 启动时，实际路径为 `**services/api/storage/`**（内含 `projects/`、`knowledge/`、`global/`、`videomaker.sqlite3`、`logs/` 等）。若从仓库根目录启动 API，则使用根目录下的 `storage/`。两套路径结构相同，请勿混用两个目录下的数据。

**关键入口文件**：


| 模块        | 入口 / 编排                                                                        |
| --------- | ------------------------------------------------------------------------------ |
| API       | `services/api/app/main.py` → `create_app()`                                    |
| 任务 SSE    | `services/api/app/routers/tasks.py`                                            |
| Worker 调度 | `services/api/app/services/pipeline_runner.py`                                 |
| 样例分析      | `services/worker/app/pipelines/p0_demo_pipeline.py` → `SampleAnalysisPipeline` |
| 生成管线      | `services/worker/app/pipelines/generation_pipeline.py`                         |
| 包装片段引擎    | `services/composition/composition/api.py` → 包装创作引擎入口                           |


---

## 技术选型


| 层级     | 技术                                               | 说明                                            |
| ------ | ------------------------------------------------ | --------------------------------------------- |
| 前端     | Next.js 15、React 19、TypeScript、Tailwind、Radix UI | 工作台页面；BFF 代理见 `apps/web/README.md`            |
| API    | Python 3.11+、FastAPI、Pydantic、SQLite             | 任务与项目元数据；本地 dev 默认库在 `services/api/storage/`  |
| Worker | Python 3.11+、httpx、jsonschema                    | 由 API `PipelineRunner` 以子进程拉起                 |
| 契约     | JSON Schema + TypeScript                         | `packages/contracts`，各模块边界                    |
| 视频感知   | FFmpeg、OpenCV、faster-whisper、yt-dlp              | `services/worker/app/tools/`                  |
| AI 模型  | 统一模型网关                                           | OpenAI 兼容对话 / 视觉；可插拔生图、TTS、生视频（DashScope、豆包等） |
| 渲染     | HyperFrames CLI（Node ≥ 22）、FFmpeg                | 默认 FFmpeg 成片；HyperFrames 用于包装片段               |
| 可观测    | 智能体调用日志、可选 Langfuse                              | `services/worker/app/observability/`          |


---

## 核心功能与亮点

### 样例理解与结构抽取

- 样例视频本地上传、链接导入（yt-dlp + 全局 Cookie）、批量上传与分析
- **算法感知 + AI 结构分析**：本地工具先提取元数据、镜头、转写、音频特征等事实，再进入 **直连多模态结构分析**（侧车 JSON + 体积/时长门禁 + 整段视频理解，非裸传视频）。竞赛演示要求配置「视频理解」Provider 并保持工作台直连开关开启（直连失败 fail-fast，不自动降级）
- **标准化结构输出**：上下文 / 口播 / 画面 / 音频四轨 + 槽位列表 + 证据链，工作台提供结构证据与四轨可视化
- **可选知识沉淀**：从样例生成「结构技能」草稿，用户审核后可 promote 至全局知识库供后续项目复用

### 新内容与素材输入

- 创作 Brief 编辑（核心主题、目标受众、创作意图等）
- 图片 / 视频 / 文案素材上传；AI 理解素材内容与高光片段（支持直接多模态分析）
- 输出「素材清单」：素材标签、可用片段、与结构槽位的语义关联，供后续匹配使用

### 结构迁移与生成

- **槽位匹配 + 缺口规划**：AI 评估 + Python 规则对齐（硬约束、变体成本策略）
- **分镜创作**：先生成全片口播稿，再展开为分镜脚本；独立生成包装（字幕样式、贴纸等）方案
- **人工审阅**（可配置关闭）：口播与分镜阶段可暂停，支持在线编辑与自然语言改稿
- **双变体并行**：默认同时生成「高点击版」与「高转化版」，支持对比与运行历史
- **多样例融合**：上传多个样例时可推荐、选型并融合结构

### 素材缺口补全

**画面类缺口**（按槽位重要性与策略链依次尝试，LLM 提议 + 规则引擎对齐后执行）：

1. 复用用户已有视频素材
2. Pexels 等图库检索（需配置 API Key）
3. HyperFrames HTML 包装片段（由包装创作智能体生成）
4. AI 生图 / 生视频（有配额管控，成本较高，权重最低）

支持「先取主素材再 HyperFrames 抛光」的组合策略；视频生成按单次生成任务配额限制。

**口播与对齐**（与画面补全分阶段，保证声画一致）：

- **仅全片口播**：系统固定为「一条 `master.wav` 覆盖全片口播稿」，不再按分镜逐段合成。  
- **人工审阅模式**：口播稿批准后，先做一次**预览语音合成 + Whisper 对齐**，得到各分镜的建议起止时间，再据此展开分镜脚本。  
- **正式生成阶段**：各槽位**画面素材补全完成后**，再合成全片口播；随后用音频实际时长**重建字幕时间轴**，并将时间线同步到口播（必要时延展末镜时长）。  
- 预览阶段若已生成同内容哈希的预览音频，正式合成会复用以节省成本。

### 成片与时间线

- 生成计划 + 渲染时间线：前端可预览迁移过程与镜头排布
- **默认 FFmpeg 输出终片 MP4**；HyperFrames 用于单镜头包装片段、特效与预览兜底
- 独立封面 `poster.jpg` 管线；结果区可预览成片，HyperFrames 片段可「入库」为可复用包装模式

### 改片与可观测性

- **成片后自然语言改片**：AI 规划改动范围 → 用户确认 → 低成本原地修改或 fork 新 generation 局部重跑
- **审阅阶段脚本改稿**：口播 / 分镜待审时可用 NL 修订
- 任务 SSE 实时进度 + 多任务面板；AI 调用日志与模型网关状态面板；可选 Langfuse 追踪

### 产品亮点（相对「直接抄样例」）

1. **可解释迁移**：结构证据、槽位映射、缺口说明、进度面板全程可见。
2. **缺口不是黑盒**：AI 提议 + 规则引擎对齐，补全链有序且可审计。
3. **人机协同**：生成可在分镜阶段暂停；支持改稿或成片后局部重跑。
4. **知识复用**：样例结构技能与 HyperFrames 包装模式可入库、推荐、绑定到新项目。
5. **渲染双轨**：FFmpeg 保证稳定 MP4；HyperFrames 承载 HTML 包装与 Agent 创作片段。

---

## 整体 AI 架构

AI 层遵循 **感知事实 → 智能体推理 → 工具执行 → 契约校验 → 产物落盘**。生产环境要求真实模型可用；`VIDEOMAKER_FIXTURE_MODE` 仅用于测试 / CI 的固定假数据，不会在 live 失败时自动降级。

### 架构分层

```text
                    ┌──────────────────────┐
                    │   模型网关           │
                    │ 文本 / 视觉 / 视频理解 │
                    │ 生图 / 语音 / 生视频   │
                    └──────────┬───────────┘
                               │
         ┌─────────────────────┼─────────────────────┐
         ▼                     ▼                     ▼
   ┌───────────┐        ┌─────────────┐       ┌──────────────┐
   │ LLM 工具  │        │ 智能体运行器 │       │ 包装片段创作网关 │
   │ + Schema  │        │ + Prompt 加载│       │（HyperFrames）  │
   └───────────┘        └─────────────┘       └──────────────┘
         │                     │                     │
         └─────────────────────┼─────────────────────┘
                               ▼
              感知工具 / 补全策略 / 渲染后端
```

- **模型网关**（`services/worker/app/gateway/model_gateway.py`）：统一调用各类模型；Provider 配置持久化在 SQLite，由 API 读写、Worker 消费。
- **智能体运行器**（`services/worker/app/agents/runner.py`）：加载 Prompt → 调用 LLM → 可选后置校验 → 记录调用日志。
- **LLM 工具**（`services/worker/app/tools/llm_tool.py`）：所有结构化输出必须过 JSON Schema 校验，失败即报错，不静默使用未校验 JSON。

### 样例分析链路

**竞赛与演示的主路径是直连多模态**（需在工作台配置「视频理解」Provider 并保持「启用直连多模态样例分析」开关为开）。该路径下**不会**在失败后自动降级到其它分析方式；直连调用失败会直接报错（`direct_multimodal_failed`），需修正配置后重试。

> 代码库仍保留早期的「分段 map-reduce」链路（关键帧 + 批次视觉 + 多智能体结构链），但是由于效果不太理想暂时遗弃，仅当**手动关闭**直连开关时才会路由到该路径——不属于竞赛演示的默认行为，也与「直连失败自动 fallback」无关。

**第一步：算法感知（直连路径同样执行）**

先用本地工具提取**可校验的客观事实**，再调用多模态模型——不是把原视频无脑丢给模型：

```text
下载 / 读取样例 → 封面 poster → FFmpeg 元数据（时长、分辨率、是否有音轨）
  → 抽音频 → Whisper 转写（软失败可继续）→ 音频特征（有无口播/BGM、节奏 onset 等）
  → OpenCV 镜头切分 → 写入 sample-analysis.json
```

**第二步：直连多模态结构抽取**

感知完成后**：**

```text
1. 门禁：样例体积 ≤ 50MB、时长 ≤ 300s（可配置），超限则拒绝直连
2. 构造「侧车文本上下文」：元数据 + 转写摘要 + 镜头列表推导的节奏事实 + 精简音频特征
   （rhythmFacts 标注为 soft_hint，供模型参考而非硬约束）
3. 多模态请求 = 系统 Prompt + 上述 JSON 上下文 + 样例 MP4（base64 附件）
4. video_structure_analyst 输出 → Schema 校验 → 结构 coercer 规范化 → 质量门禁（promoteReady 等）
```

模型同时「看到整段视频」又「读到算法已算好的事实」；该路线下结构校验会相应放宽部分反模板约束。

**收尾（可选）**

```text
knowledge_author → 项目内结构技能草稿 → 用户审核后 promote 至全局知识库
```

路由逻辑见 `services/shared/model_gateway/analysis_route.py`；E2E 验收见 `docs/demos/direct-multimodal-analysis-e2e-checklist.md`。

### 生成链路

```text
① 素材理解（content_strategist；素材多时可走直连多模态理解路线）
       ↓
[可选] 多样例选型后 structure_synthesizer 融合参考结构
       ↓
② 槽位语义匹配（slot_mapper）→ 缺口规划（gap_planner）→ 规则对齐（gap_reconcile + 变体成本策略）
       ↓
③ 脚本两阶段写作（storyboard_writer）
     · 阶段 A：全片口播稿 masterNarration + 视觉风格指引 + 口播音色偏好
     · [人工审阅] 口播稿批准
     · 预览口播：合成 preview/master.wav → Whisper 对齐 → 各镜 sceneTiming
     · 阶段 B：依据口播时长写分镜 storyboard
     · [人工审阅] 分镜批准（审阅可整体关闭，则 ③ 自动连跑）
       ↓
④ 分镜定稿后：包装设计（packaging_designer）→ 再次 reconcile 缺口（可升级「先源后抛光」）
       ↓
⑤ 组装生成计划（GenerationPlan + RenderTimeline 草案 + completionActions）
       ↓
⑥ 素材补全（generating_material）
     · 先执行各槽位画面补全（复用 / 图库 / HyperFrames 包装 / 生图 / 生视频）
     · 再合成唯一全片口播 master.wav
     · 写回分镜 visual 引用 → 时间线同步口播时长 → 字幕按 WAV 窗口对齐
       ↓
⑦ 渲染终片（默认 FFmpeg；HyperFrames 作预览或特效兜底）
```

**与旧文档的差异要点**：口播只有全片一条音轨；TTS 在画面素材就位之后执行；字幕时间来自音频对齐而非分镜字符权重占位。人工审阅模式下，分镜写作前会多一步「预览口播 + 对齐」以锁定镜头节奏。

### 主要 AI 智能体（按阶段）


| 阶段   | 智能体（代码标识）                                      | 做什么                         |
| ---- | ---------------------------------------------- | --------------------------- |
| 样例分析 | `video_structure_analyst`                      | 直连多模态：感知事实 + 整段视频理解 → 结构与证据 |
| 素材理解 | `content_strategist`、`asset_inventory_analyst` | 解析 Brief 与用户素材              |
| 结构迁移 | `slot_mapper`、`gap_planner`                    | 槽位匹配与补全规划                   |
| 分镜包装 | `storyboard_writer`、`packaging_designer`       | 口播稿、分镜、包装方案                 |
| 素材创作 | `material_author`                              | HyperFrames 包装片段（经包装片段创作引擎） |
| 知识库  | `knowledge_author`、`knowledge_selector`        | 结构技能草稿与项目选型                 |
| 改片   | `edit_intent_parser`、`revise_planner`          | 自然语言改片意图与执行计划               |


### 包装片段创作子系统（`services/composition`）

负责 **HyperFrames HTML 包装片段** 的智能创作与渲染，例如字幕条、贴纸动效、信息卡片等：

- 默认多轮 ReAct 工具循环，仅开放白名单工具：读 Skill、列 Registry、lint 草稿、提交规格  
- 流程：生成 MaterialSpec → HyperFrames lint → 渲染短 clip；满意后可 deposit / promote 为可复用「包装模式」入库

Worker 通过薄适配层 `engine_factory.py` 调用，与主生成管线解耦。

---

## 工具协议

各模块以 `**packages/contracts`** 中的 JSON Schema 为唯一数据结构来源；Python Worker 与 TypeScript 前端共用同一套定义，Worker 侧通过 `validate_contract` 校验。

### 核心契约（数据结构）


| 契约名称                        | 中文含义      | 典型用途                            |
| --------------------------- | --------- | ------------------------------- |
| `VideoStructure`            | 视频结构      | 样例分析权威结果（版本 `p1-v3`）            |
| `AssetInventory`            | 素材清单      | 创作 Brief + 可用素材描述               |
| `GapReport`                 | 缺口报告      | 槽位匹配 / 弱匹配 / 缺失情况               |
| `GenerationPlan`            | 生成计划      | 分镜、补全动作、包装、时间线草案                |
| `RenderTimeline`            | 渲染时间线     | 前端预览与 FFmpeg / HyperFrames 渲染输入 |
| `MaterialSpec`              | 包装片段规格    | HyperFrames HTML 片段定义           |
| `EditIntent` / `RevisePlan` | 改片意图 / 计划 | 自然语言改片                          |
| `ScriptDraft`               | 审阅脚本稿     | 人工审阅阶段的口播与分镜稿                   |
| `KnowledgeEntry`            | 知识库条目     | 全球结构技能或包装模式                     |
| `GenerationRun`             | 生成运行记录    | 多变体并行的一次运行                      |
| `AgentRunLog`               | 智能体调用日志   | 可观测性与调试                         |


校验命令：

```powershell
cd packages/contracts
npm run check
npm run validate:schemas
```

### 长任务协议（进度事件 + SSE）

- **权威状态**：SQLite 任务表 + 事件表
- **事件形状**：`packages/contracts/schemas/task-event.schema.json`

每条进度事件包含：任务 ID、状态、阶段名、进度百分比、消息、更新时间。

状态包括：排队、运行中、成功、失败、已取消、重试中、等待人工审阅。

阶段名覆盖感知、AI 推理、补全、渲染等细粒度步骤（如视觉事实提取、等待分镜审阅、视频生成中）。

可选附加：产物引用列表、统一错误对象。

**常用 API**：

```http
POST /api/tasks                          # 创建任务
GET  /api/tasks/{task_id}                # 查询状态
GET  /api/tasks/{task_id}/events         # SSE 推送，event: task
POST /api/tasks/{task_id}/retry          # 断点续跑，沿用同一 task_id
POST /api/tasks/{task_id}/cancel         # 取消
```

前端通过 `EventSource` 订阅（经 Next.js BFF 代理）。Worker 写入事件；API 的 `PipelineRunner` 解析子进程输出并更新任务。

### 产物引用（ArtifactRef）

登记在 SQLite 的产物元数据，指向磁盘上的视频 / 音频 / 图片 / JSON 等文件。运行时文件落在 `**{API 工作目录}/storage/projects/{项目 ID}/**` 下（开发默认 `services/api/storage/projects/...`）。

### 工具错误（ToolError）

统一错误对象：错误码、消息、是否可重试、可选详情。感知工具与补全策略失败时映射为此格式，通过进度事件或管线异常向上传递——**不会**把未校验的 AI 文本当作结构化结果使用。

### 补全策略注册

Worker 按注册表调度画面类补全（素材复用、图库检索、HyperFrames 包装、生图、生视频）以及**唯一一次全片口播合成**。每个策略输入「当前槽位上下文 + 补全动作」，输出产物路径；全部完成后统一写回生成计划、同步口播时长并对齐字幕。

---

## 安全边界

### 1. 存储路径与路径遍历

用户或 API 可控的 ID（项目 ID、生成 ID、槽位 ID、样例 ID、知识条目 ID 等）在拼磁盘路径前必须经过校验。

**共享校验逻辑**（Python 库 `services/shared/knowledge/paths.py`，被 API / Worker / 包装片段模块复用）：

- 段名仅允许字母数字与 `._-`，拒绝 `..` 与路径分隔符
- 解析后的绝对路径必须仍在配置的 `storage_root` 之下
- 违规返回 422 或 `ValueError`

**项目产物**（`services/api/app/services/artifact_store.py`）：

- 所有项目文件限制在 `{storage_root}/projects/{项目 ID}/` 内
- 测试用例显式拒绝 `../escape.txt` 类路径穿越

知识库读写、改片计划、包装模式 promote 等同样复用上述 helper。

**密钥文件位置**：`{storage_root}/global/model-gateway.key`（开发默认 `services/api/storage/global/model-gateway.key`）。

### 2. 凭证与密钥

- 模型网关与 Pexels 等第三方 Key 以 **Fernet** 加密存入 SQLite（加解密实现在 `services/shared/model_gateway/crypto.py`）
- 加密密钥文件：`{storage_root}/global/model-gateway.key`
- `GET /api/settings/model-gateway` **不返回** secret；`fixtureMode` 仅反映环境变量 `VIDEOMAKER_FIXTURE_MODE`，不可通过 API 伪造

### 3. LLM 输出边界

- 进入管线的 AI JSON 输出必须过 **JSON Schema 校验**
- 样例结构额外经 coercer 规范化，不合格即失败
- HyperFrames 包装规格在提交前必须 lint 通过
- **校验失败即任务失败**：记录日志，不静默降级为未校验 JSON

### 4. 禁止 AI 任意执行代码

- 包装片段创作 ReAct **仅暴露白名单工具**（读 Skill、列 Registry、lint、提交规格），无 shell / 任意写文件 / 动态执行
- HyperFrames 渲染通过 **固定 CLI 封装**，参数来自已校验的规格
- Worker 子进程由 API 以受控 `subprocess` 启动，环境变量白名单传递

### 5. 生产与 Fixture 模式隔离

- `VIDEOMAKER_FIXTURE_MODE=true`：使用固定假数据，供 CI 与无 Key 演示
- **生产路径要求真实模型**；live 失败时不自动回退 fixture
- 前端 `VIDEOMAKER_USE_FIXTURE_FALLBACK` 仅在上游 API 不可达时展示演示数据，与 Worker 生产逻辑分离

### 6. 配额与成本护栏

- 视频生成：每槽位 / 每次 generation 配额上限
- 样例分析（直连多模态模型）：单次视频理解调用；样例体积 / 时长门禁（默认 ≤ 50MB、≤ 300s，超限 fail-fast）
- 缺口对齐：按变体偏好排序补全策略，限制昂贵链路

### 7. 内容合规取向

- 系统设计为**结构迁移**而非像素级复制；Prompt 与管线分离「样例方法」与「新主题素材」
- 样例视频内容不作为生成目标明文写入成片脚本（分镜基于新 Brief 创作）

---

## 快速开始

### 环境要求

- **Node.js** ≥ 22（HyperFrames CLI）
- **Python** ≥ 3.11
- **FFmpeg** 在 PATH 上
- **根目录 `npm install`**：成片渲染与 HyperFrames 包装片段需要（仅浏览工作台可不装）
- **模型 API Key**：Live 演示必需，在工作台 **模型服务** 配置（见下方「模型配置」）；Fixture 模式可跳过

### 安装

```powershell
# 根目录 HyperFrames CLI
cd D:\VideoMaker
npm install

# 契约
cd packages/contracts
npm install

# API（uv 推荐）
cd services/api
uv venv .venv
uv pip install --python .venv\Scripts\python.exe -r pyproject.toml

# Web
cd apps/web
Copy-Item .env.example .env.local
npm install
```

### 启动

需 **两个终端** 分别运行 API 与 Web。浏览器打开 [http://localhost:3000/projects](http://localhost:3000/projects)。

**终端 1 — API**（默认 `http://127.0.0.1:8000`；Worker 样例分析 / 生成由 API 子进程拉起，无需单独启动）

```powershell
cd services/api
# Live 演示：在运行 run-dev.ps1 之前设置（见下方「模型配置」）
.\run-dev.ps1
```

**终端 2 — Web**（默认 `http://localhost:3000`）

```powershell
cd apps/web
Copy-Item .env.example .env.local   # 首次
npm run dev
```

Web 通过 BFF 代理访问 API，服务端环境变量 `VIDEOMAKER_API_URL` 默认 `http://127.0.0.1:8000`（见 `apps/web/.env.example` 与 `apps/web/README.md`）。**不要**把后端地址暴露给浏览器直连。

> **存储路径**：`run-dev.ps1` 在 `services/api` 目录下启动 API，运行时数据默认写入 `services/api/storage/`（含 `videomaker.sqlite3`、模型网关加密密钥 `global/model-gateway.key` 等），而非仓库根目录的 `storage/`。

### 模型配置

系统依赖 **Model Gateway** 统一管理 LLM / 多模态 / 生图 / TTS / 生视频等 Provider。凭据保存在 **`{storage_root}/videomaker.sqlite3`**，API Key 经 **`global/model-gateway.key`** 加密；`GET /api/settings/model-gateway` **不返回** secret。

| 模式 | 适用 | API 终端环境变量 | 模型 Key |
| --- | --- | --- | --- |
| **Live** | 竞赛演示、真实样例分析与生成 | `VIDEOMAKER_FIXTURE_MODE=false`（或未设置且不为 `true`） | 工作台 **设置 → 模型服务** 配置 |
| **Fixture** | 无 Key 冒烟、CI、仅测 UI / 任务流 | `VIDEOMAKER_FIXTURE_MODE=true` | 无需填写 |

**Live 演示最小配置（工作台 UI）**

1. 启动后打开 `/projects` 进入项目，在 **模型服务** 面板配置并保存：
   - **文本**（生成 / 改片等 Agent 必需）
   - **生图**（缺口 AIGC 补图时需要）
2. **样例分析（直连多模态）**：额外配置 **视频理解** Provider，并保持 **「启用直连多模态样例分析」** 为开启（设置页可预览当前将使用的分析路线）。
3. 按需配置 **视觉**、**配音（TTS）**、**生视频**；豆包语音 Key 与火山方舟 Key 为不同凭据，须分别填写。

也可通过 API 写入：`PUT /api/settings/model-gateway`（详见 `docs/demos/p1-manual-test-guide.md` §1.3）。

**启动预检**

```powershell
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/api/settings/model-gateway
```

期望：`health` 返回 `{"ok":true}`；gateway 返回各 Provider 就绪状态，**不含** API Key 明文。

**可选环境变量（API 终端，Live 演示常用）**

```powershell
$env:VIDEOMAKER_FIXTURE_MODE = "false"
$env:VIDEOMAKER_DEFAULT_VARIANTS = "high_click,high_conversion"
```

完整 E2E 与模型相关验收见 `docs/demos/p1-manual-test-guide.md`、`docs/demos/direct-multimodal-analysis-e2e-checklist.md`。

### 常用验证

```powershell
cd packages/contracts && npm run check && npm run validate:schemas
cd services/api && python -m pytest
cd services/worker && python -m pytest
cd apps/web && npm run typecheck && npm run test
```

---

## 数据存储说明

本项目的**运行时产物与 SQLite 元数据**不在 Git 中跟踪，统一落在 `**{启动 API 时的当前工作目录}/storage/`**。


| 场景                           | 实际路径（本仓库示例）                           |
| ---------------------------- | ------------------------------------- |
| 按快速开始从 `services/api` 启动（推荐） | `D:\VideoMaker\services\api\storage\` |
| 从仓库根目录启动 API                 | `D:\VideoMaker\storage\`              |


代码入口：`services/api/app/main.py` 中 `storage_root = Path.cwd() / "storage"`。Worker 子进程通过 API 传入的 `storageRoot` 读写同一目录，不会自行猜测仓库根路径。

**目录结构**（两种启动方式下结构相同）：

```text
storage/
├── videomaker.sqlite3      # 任务、项目、知识库索引等元数据
├── projects/{projectId}/   # 样例、素材、生成产物、checkpoint
├── knowledge/{category}/   # 已 promote 的全球结构技能 / 包装模式
├── global/                 # 全局 Cookie、模型网关密钥文件等
└── logs/                   # API / Worker 日志（dev_server 写入）
```

开发时若发现根目录 `storage/` 几乎为空、而 `services/api/storage/` 下有完整项目数据，属于正常现象——请以 **API 进程 cwd 对应的路径** 为准。

---

## 仓库结构

```text
VideoMaker/
├── apps/web/                 # Next.js 工作台（浏览器 UI）
├── packages/
│   ├── contracts/            # JSON Schema + TypeScript 类型（模块间契约）
│   └── prompts/              # AI 智能体 Prompt 模板
├── services/
│   ├── api/                  # FastAPI 服务（含 dev 默认 storage/ 与 SQLite）
│   ├── worker/               # 视频感知、AI 编排、补全、渲染
│   ├── composition/          # HyperFrames 包装片段创作引擎
│   └── shared/               # API / Worker 共用 Python 库（见下）
├── skills/                   # HyperFrames 官方与项目私有 Skill
├── storage/                  # 可选：从仓库根启动 API 时的运行时目录（gitignore）
├── docs/                     # 设计规格、计划与 E2E 清单
├── VideoMaker.md             # 竞赛课题说明
└── AGENTS.md                 # AI 开发上下文（模块状态与 API 索引）
```

`**services/shared` 是什么？** 不是磁盘上的「知识库文件夹」，而是 **Python 共享代码包**，被 API 与 Worker 共同 import，主要包括：


| 子模块              | 作用                                         |
| ---------------- | ------------------------------------------ |
| `model_gateway/` | 模型 Provider 配置的 SQLite 读写、加密、TTS 偏好、分析路线预览 |
| `knowledge/`     | 知识库**文件**路径安全校验、索引构建、推荐逻辑                  |
| `stock_media/`   | Pexels 等图库 API Key 的加密存储                   |
| `structure/`     | 结构槽位角色等跨服务常量                               |
| `video/`         | 封面 poster 等共用视频工具                          |


全球知识库的**文件内容**仍落在 `{storage_root}/knowledge/`；`services/shared/knowledge/` 提供的是操作这些文件的 Python 逻辑。

---

## 验证与演示


| 文档                                                                           | 内容                              |
| ---------------------------------------------------------------------------- | ------------------------------- |
| `[docs/demos/p1-demo-checklist.md](./docs/demos/p1-demo-checklist.md)`       | 端到端演示清单                         |
| `[docs/demos/p1-manual-test-guide.md](./docs/demos/p1-manual-test-guide.md)` | 手动测试步骤                          |
| `docs/demos/*-e2e-checklist.md`                                              | 知识库、多样例、NL 改片、FFmpeg 渲染、口播对齐等专题 |


---

## 许可证与说明

本项目为竞赛/课题研究用途。第三方模型与媒体 API 的使用须遵守各自服务条款；Pexels 等图库素材需保留出处标注。

如有新功能开发，请先阅读 `[AGENTS.md](./AGENTS.md)` 与 `docs/superpowers/plans/` 下对应模块计划，并优先修改 `packages/contracts` 再改依赖方。