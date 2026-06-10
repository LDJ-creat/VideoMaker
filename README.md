# VideoMaker — 爆款结构迁移引擎

> 从优质样例拆解创作结构，识别素材缺口，迁移到新主题与素材，生成可解释的分镜、时间线与成片 demo。

本项目为剪映 AI 创作竞赛课题实现：**不复制样例内容，而是迁移「创作方法」**——脚本段落、镜头节奏、包装样式等可复用结构，并在素材不足时通过补全策略完成成片。

更完整的开发上下文与模块状态见 [`AGENTS.md`](./AGENTS.md)；架构规格见 [`docs/superpowers/specs/2026-05-27-videomaker-design.md`](./docs/superpowers/specs/2026-05-27-videomaker-design.md)。

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
- [仓库结构](#仓库结构)
- [验证与演示](#验证与演示)

---

## 项目主题与目标

**课题名称**（见 [`VideoMaker.md`](./VideoMaker.md)）：爆款结构迁移引擎 — 从样例拆解、素材补全到视频重组的 AI 创作平台。

系统打通的核心闭环：

```text
样例视频输入（支持批量 / 知识库上下文）
  → 感知层提取事实（FFmpeg / OpenCV / Whisper 等）
  → LLM 结构分析（structure_analyst 等）→ VideoStructure
  → 新 Brief + 素材理解（content_strategist / asset_inventory_analyst）
  → 语义槽位映射 + 缺口规划（slot_mapper / gap_planner）
  → 分镜与包装（storyboard_writer / packaging_designer）
  → 人工审阅闸门（全片口播 / 分镜，可配置）
  → 素材补全（资产复用 / 图库 / AIGC / HyperFrames / TTS）
  → RenderTimeline → FFmpeg 或 HyperFrames 成片
  → 可选 NL 改片、双变体对比、知识沉淀与 Composition Pattern 入库
```

评分维度对应实现：结构定义清晰（`VideoStructure` 四轨 + 证据链）、迁移可解释（工作台可视化）、缺口可识别（`GapReport`）、过程可见（SSE 任务进度 + Agent Run 日志）、结果可验证（分镜 / 时间线 / MP4）。

---

## 整体架构

采用**前后端分离 + 契约驱动**的单仓多模块布局：

```text
┌─────────────────────────────────────────────────────────────────┐
│  apps/web          Next.js 工作台（BFF 代理 /api → FastAPI）     │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTP + SSE (TaskEvent)
┌────────────────────────────▼────────────────────────────────────┐
│  services/api      FastAPI：项目/样例/生成/知识库/设置/任务 API   │
│                    SQLite 任务元数据 + PipelineRunner 调度 Worker │
└────────────────────────────┬────────────────────────────────────┘
                             │ subprocess + env（同 task_id，resume）
┌────────────────────────────▼────────────────────────────────────┐
│  services/worker   感知管线 + Agent 编排 + 补全 + 渲染            │
│  services/composition  HyperFrames MaterialSpec / ReAct 作者引擎   │
│  services/shared     model_gateway、知识库路径、stock_media 等   │
└────────────────────────────┬────────────────────────────────────┘
                             │ 读写产物
┌────────────────────────────▼────────────────────────────────────┐
│  storage/          projects/{projectId}/、knowledge/、global/     │
│  packages/contracts TypeScript 类型 + JSON Schema（模块边界）      │
│  packages/prompts   Agent Prompt 模板                              │
└─────────────────────────────────────────────────────────────────┘
```

**任务与状态权威来源**：SQLite 中的 `tasks` 表 + `TaskEvent` 流；前端以 SSE 为主、轮询为兜底。长任务支持 **checkpoint 断点续跑**（`storage/projects/{projectId}/.../checkpoint.json`），重试使用 `POST /api/tasks/{task_id}/retry` 且保持同一 `task_id`。

**关键入口文件**：

| 模块 | 入口 / 编排 |
|------|-------------|
| API | `services/api/app/main.py` → `create_app()` |
| 任务 SSE | `services/api/app/routers/tasks.py` |
| Worker 调度 | `services/api/app/services/pipeline_runner.py` |
| 样例分析 | `services/worker/app/pipelines/p0_demo_pipeline.py` → `SampleAnalysisPipeline` |
| 生成管线 | `services/worker/app/pipelines/generation_pipeline.py` |
| Composition | `services/composition/composition/api.py` → `CompositionEngine` |

---

## 技术选型

| 层级 | 技术 | 说明 |
|------|------|------|
| 前端 | Next.js 15、React 19、TypeScript、Tailwind、Radix UI | 工作台 `/projects`、`/projects/{id}`；BFF 见 `apps/web/README.md` |
| API | Python 3.11+、FastAPI、Pydantic、SQLite | 本地元数据与任务状态 |
| Worker | Python 3.11+、httpx、jsonschema | 子进程由 API `PipelineRunner` 拉起 |
| 契约 | JSON Schema Draft 2020-12 + TS 类型 | `packages/contracts` |
| 视频感知 | FFmpeg、OpenCV、faster-whisper (Whisper)、yt-dlp | `services/worker/app/tools/` |
| LLM / 多模态 | ModelGateway：OpenAI 兼容 Chat / Vision / Image / TTS / Video | 可插拔 Provider（DashScope Wan、豆包 Seed TTS 等） |
| 渲染 | HyperFrames CLI（Node ≥ 22）、FFmpeg 后端 | 默认 FFmpeg 成片；HF 用于 slot 素材与特效兜底 |
| 可观测 | AgentRunLog、可选 Langfuse | `services/worker/app/observability/` |

---

## 核心功能与亮点

### 样例理解与结构抽取

- 样例视频本地上传、URL 导入（yt-dlp + 全局 Cookie）、批量上传与分析
- 感知层：元数据、镜头检测、Whisper ASR、关键帧、音频特征、批次视觉理解（成本与深度可配置）
- LLM 结构分析：`structure_analyst` 及分段 / 关键帧 / 编译 / 质检 Agent 链；可选 `videoUnderstanding` 直连多模态分析
- 标准化输出 `VideoStructure`（四轨：context / verbal / visual / audio + slots / evidence），工作台结构证据与四轨 UI
- 可选知识草稿：`knowledge_author` 生成 structure skill，支持 promote 至全球知识库

### 新内容与素材输入

- Brief 编辑（UserBrief v2）、商品卖点与创作意图
- 图片 / 视频 / 文案素材上传；`content_strategist` 与 `asset_inventory_analyst`（支持直接多模态素材理解）
- `AssetInventory`：高光片段、视觉标签、素材与结构槽位的语义关联输入

### 结构迁移与生成

- `slot_mapper` 语义槽位匹配 + `gap_planner` 缺口规划；`gap_reconcile` 将 LLM 提议与硬规则、变体成本策略对齐
- `storyboard_writer`：全片 `masterNarration` + 分镜脚本；`packaging_designer` 包装方案
- 人工审阅闸门（可配置）：全片口播与分镜阶段暂停，`script-draft.json` 编辑与 NL 修订
- 双变体并行生成（默认 `high_click`、`high_conversion`），变体对比与 Generation Run 历史
- 多样例：`structure_synthesizer` 融合多样例结构；样例推荐与项目级样例选型

### 素材缺口补全

- 补全 Provider 链：`asset_reuse` → `stock_media_search`（Pexels）→ `hyperframes_material` → `image_generation` → `video_generation` → `tts`
- `source_then_polish`：主源素材 + HyperFrames finish 抛光；视频生成按 generation 配额管控
- 全片口播（Global TTS）或分镜 TTS；字幕与 WAV 对齐、`hold_tail` 时间线延展
- Composition Agent：`material_author` ReAct 创作 `MaterialSpec`，pattern deposit / promote 入库

### 成片与时间线

- `GenerationPlan` + `RenderTimeline`；时间线预览与迁移过程可视化
- 默认 FFmpeg 终片 MP4；HyperFrames 用于 slot 片段、包装特效与预览兜底
- 封面 `poster.jpg` 独立管线；结果区成片预览与 Composition Pattern  promote

### 改片与可观测性

- 成片后 NL 改片：`revise_planner` → 用户确认 → plan / execute（低成本 in-place 或 fork 新 generation）
- 审阅阶段脚本 NL 修订：`script-draft/nl-revise`
- 任务 SSE + 多任务进度面板；`AgentRunLog` 与 Model Gateway 状态面板；可选 Langfuse

### 产品亮点（相对「直接抄样例」）

1. **可解释迁移**：结构证据、槽位映射、缺口说明、迁移进度面板全程可见。
2. **缺口不是黑盒**：LLM 提议 + Python `gap_reconcile`  reconcile，补全链有序且可审计。
3. **人机协同**：生成可在分镜阶段暂停；NL 修订脚本或成片后局部重跑。
4. **知识复用**：结构技能与 Composition Pattern 可入库、推荐、绑定到新项目。
5. **渲染双轨**：FFmpeg 保证稳定 MP4；HyperFrames 承载 HTML 包装与 Agent 创作片段。

---

## 整体 AI 架构

AI 层分为 **感知事实 → Agent 推理 → 工具执行 → 契约校验 → 产物落盘**，生产路径**不以规则语义兜底**（`VIDEOMAKER_FIXTURE_MODE` 仅用于测试/CI）。

### 架构分层

```text
                    ┌──────────────────────┐
                    │   ModelGateway       │
                    │ text / vision /      │
                    │ video_understanding  │
                    │ image / tts / video  │
                    └──────────┬───────────┘
                               │
         ┌─────────────────────┼─────────────────────┐
         ▼                     ▼                     ▼
   ┌───────────┐        ┌─────────────┐       ┌──────────────┐
   │ LLMTool   │        │ AgentRunner │       │ ToolGateway  │
   │ + Schema  │        │ + PromptLoader│     │ (Composition)│
   └───────────┘        └─────────────┘       └──────────────┘
         │                     │                     │
         └─────────────────────┼─────────────────────┘
                               ▼
              perception tools / completion providers / render
```

- **ModelGateway**（`services/worker/app/gateway/model_gateway.py`）：统一 `complete_json`、多 profile Chat、TTS、图像与异步视频任务；配置来自 API SQLite `model_gateway_providers`（经 `ModelGatewayStore`）。
- **AgentRunner**（`services/worker/app/agents/runner.py`）：加载 Prompt → 调用 `LLMTool.generate_json` → 可选 `post_validate` → 记录 `AgentRunLog`。
- **LLMTool**（`services/worker/app/tools/llm_tool.py`）：输出必须经 `validate_contract(schema_name)`；校验失败抛 `LLMToolValidationError`。

### 样例分析链路

```text
SampleAnalysisPipeline (算法感知)
  metadata / shots / whisper / keyframes / audioProfile / batch vision
       ↓
resolve_structure_analysis_route
  ├─ perception + structure_analyst (+ segment/keyframe agents, critic, compiler)
  └─ direct multimodal: direct_video_structure_pipeline
       ↓
structure_coercer / StructureValidationError
       ↓
可选 knowledge_author → 项目 knowledge draft
```

实现锚点：`services/worker/app/pipelines/sample_pipeline.py`、`structure_analysis_pipeline.py`、`p0_demo_pipeline.analyze_sample()`。

### 生成链路

```text
content_strategist (+ asset_inventory_analyst 多模态路由)
       ↓
可选 structure_synthesizer（多样例）
       ↓
slot_mapper → classify_slot_matches
       ↓
gap_planner → gap_reconcile（硬规则 + variant preferProviders）
       ↓
storyboard_writer（masterNarration 两阶段）
       ↓
[human review gates]
       ↓
packaging_designer
       ↓
planning_completion → execute_completion_plan
  providers: asset_reuse | stock_media_search | hyperframes_material
             | image_generation | video_generation | tts
       ↓
narration_alignment + timeline sync
       ↓
resolve_render_backend → ffmpeg | hyperframes
```

实现锚点：`services/worker/app/pipelines/generation_pipeline.py`、`gap_reconcile.py`、`providers/completion_registry.py`。

### Agent 职责一览

| Agent | 职责 |
|-------|------|
| `structure_analyst` / `video_structure_analyst` | 样例结构抽取与证据 |
| `segment_proposer` / `segment_analyst` / `keyframe_batch_analyst` | 分段与视觉批次理解 |
| `structure_compiler` / `structure_critic` | 结构编译与质检 |
| `content_strategist` | Brief 与内容策略 |
| `asset_inventory_analyst` | 素材库多模态理解 |
| `slot_mapper` | 语义槽位匹配 |
| `gap_planner` | 缺口与补全提议 |
| `storyboard_writer` | 全片口播 + 分镜脚本 |
| `packaging_designer` | 包装方案 |
| `material_author` | HyperFrames 素材片段（经 CompositionEngine） |
| `composition_pattern_author` | Pattern 泛化入库 |
| `knowledge_author` / `knowledge_selector` | 知识草稿与选型 |
| `structure_synthesizer` | 多样例结构融合 |
| `edit_intent_parser` / `revise_planner` | NL 改片意图与计划 |
| `stock_query_author` | 图库检索查询生成 |

Prompt 版本化：`packages/prompts` + `PromptLoader`。

### Composition 子系统

`services/composition` 提供 **MaterialSpec 创作引擎**：

- `CompositionEngine.author_material_spec` → ReAct 循环（默认 `VIDEOMAKER_COMPOSITION_AGENT_MODE=react`）
- 白名单工具：`skill_view`、`registry_list`、`composition_lint_draft`、`submit_material_spec`（见 `composition/author/tools.py`）
- `build_composition` → `hyperframes lint` → `render_clip`；Pattern `deposit` / `promote` 经 relint 门禁

Worker 通过薄适配层 `services/worker/app/composition/engine_factory.py` 调用。

---

## 工具协议

模块间以 **`packages/contracts`** 为唯一 JSON 形状来源；Python Worker 通过 `app/validation/schema_loader.validate_contract` 与 TypeScript 共用同一套 Schema。

### 核心契约类型

| Schema | 用途 |
|--------|------|
| `VideoStructure` | 样例结构权威结果（契约版本 `p1-v3`） |
| `AssetInventory` | Brief 与可用素材 |
| `GapReport` | 匹配 / 弱匹配 / 缺失槽位 |
| `GenerationPlan` | 分镜、补全动作、包装、时间线草案 |
| `RenderTimeline` | 前端时间线预览与渲染后端输入 |
| `MaterialSpec` | HyperFrames 片段规格（含 `template=composition`） |
| `EditIntent` / `RevisePlan` | NL 改片 |
| `ScriptDraft` | 人工审阅脚本稿 |
| `KnowledgeEntry` | 全球知识库条目（structure / composition_pattern） |
| `GenerationRun` | 多变体运行记录 |
| `AgentRunLog` | Agent 调用可观测性 |

校验命令：

```powershell
cd packages/contracts
npm run check
npm run validate:schemas
```

### 长任务协议（TaskEvent + SSE）

- **权威状态**：SQLite `tasks` + `task_events`（`TaskEventService`）
- **事件形状**：`packages/contracts/schemas/task-event.schema.json`

必填字段：`taskId`、`status`、`stage`、`progress`、`message`、`updatedAt`。

`status` 含 `queued | running | succeeded | failed | cancelled | retrying | awaiting_review`。

`stage` 枚举覆盖感知、Agent、补全、渲染等细粒度阶段（如 `extracting_visual_facts`、`awaiting_storyboard_review`、`generating_video`）。

可选字段：

- `artifactRefs[]` → `ArtifactRef`
- `error` → `ToolError`

**API 路由**：

```http
POST /api/tasks
GET  /api/tasks/{task_id}
GET  /api/tasks/{task_id}/events    # SSE，event: task
POST /api/tasks/{task_id}/retry    # resume=true，同一 task_id
POST /api/tasks/{task_id}/cancel
```

前端：`EventSource('/api/tasks/{taskId}/events')`（经 Next BFF 代理）。

Worker 通过 `TaskContext.emit_event` 写入；API `PipelineRunner` 将子进程 stdout 解析为任务更新。

### 产物引用（ArtifactRef）

```json
{
  "id": "uuid",
  "type": "video | audio | image | json | text | html | render",
  "uri": "绝对或 storage 路径",
  "createdAt": "ISO-8601"
}
```

API `ArtifactStore.register_artifact` 将产物登记到 SQLite `artifacts` 表；运行时文件落在 `storage/projects/{projectId}/`。

### 工具错误（ToolError）

统一错误对象：`code`、`message`、`retryable`、可选 `details`。感知工具（FFmpeg / Whisper 等）与补全 Provider 失败时映射为 `ToolError`，通过 `TaskEvent.error` 或管线异常向上传递，**不**将未校验的 LLM 文本当作结构化产物。

### 补全 Provider 协议

`completion_registry` 注册的可执行 Provider：

`asset_reuse`、`stock_media_search`、`hyperframes_material`、`image_generation`、`video_generation`、`tts`。

每个 Provider 实现 `CompletionStrategyProvider`：输入 `MaterialContext` + action 字典，输出 `MaterialResult`（含 artifact 路径），由 `apply_material_results_to_plan` 写回 `GenerationPlan` / `RenderTimeline`。

---

## 安全边界

### 1. 存储路径与路径遍历

用户或 API 可控的 ID（`projectId`、`generationId`、`slotId`、`sampleId`、`entryId` 等）在拼路径前必须经过校验。

**共享规则**（`services/shared/knowledge/paths.py`）：

- `validate_storage_segment`：非空、≤128 字符、仅 `[A-Za-z0-9._-]`，拒绝 `.`、`..`、`/`、`\`
- `assert_under_storage_root` / `resolve_storage_path`：解析后必须仍在 `storage_root` 下
- 违规 → `ValueError("invalid_{field}")` 或 `path_escape_storage_root`（API 映射为 422）

**项目产物**（`services/api/app/services/artifact_store.py`）：

- `resolve_project_path(project_id, relative_path)` 限制在 `storage/projects/{projectId}/` 内
- 测试用例显式拒绝 `../escape.txt`（`services/api/tests/test_artifact_store.py`）

知识库、改片计划、Composition promote 等路径均复用上述 helper（如 `knowledge_store.py`、`revise_plan_service.py`）。

### 2. 凭证与密钥

- Model Gateway 与 Pexels 等第三方 Key 以 **Fernet** 加密存入 SQLite（`services/shared/model_gateway/crypto.py`）
- 密钥文件：`storage/global/model-gateway.key`
- `GET /api/settings/model-gateway` **不返回** secret；仅报告就绪状态与 `fixtureMode`（来自环境变量 `VIDEOMAKER_FIXTURE_MODE`，**不可通过 PUT 伪造**）

### 3. LLM 输出边界

- 所有进入管线的 Agent JSON 经 **JSON Schema 校验**（`validate_contract`）
- 结构分析额外经 `structure_coercer` / `StructureValidationError`
- `MaterialSpec` / Composition 在 `submit_material_spec` 前 `composition_lint_draft`
- **校验失败即失败**：抛 `LLMToolValidationError`，记录 `AgentRunLog.output_valid=false`，不静默降级到未校验 JSON

### 4. 禁止 LLM 任意执行代码

- Composition ReAct **仅暴露白名单工具**（读 Skill、列 Registry、lint、提交 Spec），无 shell / 任意文件写 / 动态 `exec`
- HyperFrames 渲染通过 **固定 CLI 封装**（`HyperFramesCli`），参数由已校验的 `MaterialSpec` 与构建上下文生成
- Worker 子进程由 API `PipelineRunner` 以受控 `subprocess` 启动，环境变量白名单传递（如 fixture mode、Pexels key）

### 5. 生产与 Fixture 模式隔离

- `VIDEOMAKER_FIXTURE_MODE=true`：使用 fixture LLM / 媒体工具，供 CI 与本地无 Key 演示
- **生产路径要求 live ModelGateway**；live 模型失败时**不**自动回退 fixture（AGENTS.md 锁定行为）
- 前端 `VIDEOMAKER_USE_FIXTURE_FALLBACK` 仅在 BFF 上游不可达时展示演示数据，与 Worker 生产逻辑分离

### 6. 配额与成本护栏

- 视频生成：`VIDEOMAKER_VIDEO_GEN_MAX_PER_SLOT` / 每 generation 配额（`VideoGenQuota`）
- 样例分析：vision batch 次数、关键帧上限、`analysisDepth` 控制成本
- Gap reconcile：按 variant `preferProviders` 排序，限制昂贵 Provider 链

### 7. 内容合规取向

- 系统设计为**结构迁移**而非像素级复制；Prompt 与管线分离「样例方法」与「新主题素材」
- 样例视频内容不作为生成目标明文写入成片脚本（由 `storyboard_writer` 基于新 Brief 创作）

---

## 快速开始

### 环境要求

- **Node.js** ≥ 22（HyperFrames CLI）
- **Python** ≥ 3.11
- **FFmpeg** 在 PATH 上
- 可选：GPU / 模型 API Key（生产路径）

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
cp .env.example .env.local
npm install
```

### 启动

```powershell
# API（默认 http://127.0.0.1:8000）
cd services/api
.\run-dev.ps1

# Web（默认 http://localhost:3000）
cd apps/web
npm run dev
```

Web 通过 BFF 访问 API：`VIDEOMAKER_API_URL=http://127.0.0.1:8000`（见 `apps/web/README.md`）。

### 常用验证

```powershell
cd packages/contracts && npm run check && npm run validate:schemas
cd services/api && python -m pytest
cd services/worker && python -m pytest
cd apps/web && npm run typecheck && npm run test
```

---

## 仓库结构

```text
VideoMaker/
├── apps/web/                 # Next.js 工作台
├── packages/
│   ├── contracts/            # JSON Schema + TypeScript 类型
│   └── prompts/              # Agent Prompt 模板
├── services/
│   ├── api/                  # FastAPI 服务
│   ├── worker/               # 感知 + Agent + 补全 + 渲染
│   ├── composition/          # HyperFrames Composition 引擎
│   └── shared/               # model_gateway、paths、knowledge 共享库
├── skills/                   # HyperFrames 官方与私有 Skill
├── storage/                  # 运行时产物（gitignore）
├── docs/                     # 设计规格、计划与 E2E 清单
├── VideoMaker.md             # 竞赛课题说明
└── AGENTS.md                 # AI 开发上下文（模块状态与 API 索引）
```

---

## 验证与演示

| 文档 | 内容 |
|------|------|
| [`docs/demos/p1-demo-checklist.md`](./docs/demos/p1-demo-checklist.md) | 端到端演示清单 |
| [`docs/demos/p1-manual-test-guide.md`](./docs/demos/p1-manual-test-guide.md) | 手动测试步骤 |
| `docs/demos/*-e2e-checklist.md` | 知识库、多样例、NL 改片、FFmpeg 渲染、口播对齐等专题 |

---

## 许可证与说明

本项目为竞赛/课题研究用途。第三方模型与媒体 API 的使用须遵守各自服务条款；Pexels 等图库素材需保留 attribution（`stock-attribution` 契约）。

如有新功能开发，请先阅读 [`AGENTS.md`](./AGENTS.md) 与 `docs/superpowers/plans/` 下对应模块计划，并优先修改 `packages/contracts` 再改依赖方。
