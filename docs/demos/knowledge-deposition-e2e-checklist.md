# 知识库与经验沉淀 — 端到端测试方案与清单

> **适用范围：** VideoMaker「知识库与经验沉淀落地」功能（2026-06-03 实现）  
> **目标：** 在真实运行环境（API + Worker + Web）中验证完整用户路径、存储落盘、自动推荐绑定、生成链路渐进披露与审查修复项。  
> **预计耗时：** Fixture 模式约 45–60 分钟；Live LLM 模式另加 30 分钟。

---

## 1. 测试范围

### 1.1 In Scope（必须验证）

| 能力 | 验收要点 |
|------|----------|
| 样例分析 → 知识草稿 | `rendering_knowledge_draft` 阶段、draft 三文件落盘 |
| Promote → 全局库 | `storage/knowledge/{category}/{entryId}/` + SQLite `knowledge_entries` |
| Brief / generation-plan 自动 recommend + bind | `ensure_selection`、Top-1 绑定 |
| 无样例项目生成 | auto-apply knowledge 为 `source_kind=knowledge` 样例 |
| 有真实样例时 knowledge 仅参考 | 生成用真实 structure，不覆盖；手动 apply 被拦截 |
| 用户 override / reset | `mode=user_override` 不被 auto 覆盖；恢复自动选用 |
| 前端工作台 | 录入区推荐面板、知识库 Tab、草稿 promote、全局浏览 |
| Agent 渐进披露 | 生成时 `knowledgeContext` 注入（L1 默认；弱匹配多时可观测 L2） |

### 1.2 Out of Scope（本清单不阻塞发版）

- 向量 embedding 检索
- 知识 merge / 长期进化
- `versions/v{n}/` 自动归档
- 多用户并发 / 生产级压测

---

## 2. 环境与前置条件

### 2.1 依赖检查

```powershell
# 仓库根 — HyperFrames（生成预览用，可选）
cd D:\VideoMaker
npm run hyperframes:doctor

# Node >= 22、FFmpeg 在 PATH（样例分析需要）
node -v
ffmpeg -version
```

### 2.2 启动服务

**终端 1 — API（含 Worker 子进程）：**

```powershell
cd D:\VideoMaker\services\api
.\run-dev.ps1
# 确认 http://localhost:8000/health → {"ok":true}
```

**终端 2 — Web：**

```powershell
cd D:\VideoMaker\apps\web
npm run dev
# 浏览器 http://localhost:3000/projects
```

### 2.3 推荐测试模式

| 模式 | 环境变量 | 适用场景 |
|------|----------|----------|
| **Fixture（默认）** | API 进程 `VIDEOMAKER_FIXTURE_MODE=true`（或未配置） | 快速 E2E、无 API Key |
| **Live LLM** | `VIDEOMAKER_FIXTURE_MODE=false` + Workbench 配置 ModelGateway text 提供商 | knowledge_author 真实 MD、可选 knowledge_selector 重排 |

### 2.4 测试前自动化冒烟（建议先跑）

```powershell
cd D:\VideoMaker\packages\contracts
npm run check; npm run validate:schemas

cd D:\VideoMaker\services\shared
python -m pytest tests/test_knowledge_*.py -q

cd D:\VideoMaker\services\worker
python -m pytest tests/test_knowledge_*.py tests/test_p0_demo_pipeline_knowledge.py -q

cd D:\VideoMaker\services\api
python -m pytest tests/test_knowledge_routes.py -q --basetemp=$env:TEMP\vm-pytest-api

cd D:\VideoMaker\apps\web
npm run typecheck; npm run test
```

全部通过后再开始手动 E2E。

### 2.5 测试素材建议

- **样例视频：** 15–60 秒短视频 MP4（本地文件即可；或已配置 cookies 的 URL 导入）
- **Brief 主题 A（匹配电商条目）：** topic=`电商带货`，sellingPoints=`["限时优惠","包邮"]`
- **Brief 主题 B（不匹配）：** topic=`教育科普`，sellingPoints=`["学习方法"]`

---

## 3. 端到端场景

### 场景 0：健康检查与空库基线

| 步骤 | 操作 | 预期 |
|------|------|------|
| 0.1 | `GET /health` | `200`，`ok: true` |
| 0.2 | `GET /api/knowledge/entries` | `200`，`entries: []`（或仅历史数据） |
| 0.3 | 新建项目 `Knowledge E2E Seed` | 进入工作台，无报错 |

**记录：** 项目 ID = `________________`

---

### 场景 A：样例分析 → 知识草稿 → Promote（沉淀主路径）

**目的：** 验证 Worker draft 落盘 + API promote + 全局库索引。

| # | 步骤 | UI / API | 预期结果 | ✓ |
|---|------|----------|----------|---|
| A.1 | 上传样例 MP4 | 录入 → 上传样例视频 | 出现 taskId，进度面板可追踪 | ☐ |
| A.2 | 等待样例分析完成 | 进度 → 样例分析 | 元信息/转写/镜头/结构可见 | ☐ |
| A.3 | 观察任务阶段 | 进度面板 stage 标签 | 出现 **「生成知识草稿」**（`rendering_knowledge_draft`） | ☐ |
| A.4 | 查看知识草稿 | 样例分析页 或 **知识库** Tab | **知识草稿** 卡片 + Markdown 预览 | ☐ |
| A.5 | 检查 draft 文件 | 文件系统 | 存在 `storage/projects/{projectId}/knowledge/drafts/{sampleId}/` 下：<br>• `structure-skill.md`<br>• `video-structure.json`<br>• `entry-meta.json` | ☐ |
| A.6 | API 读取 draft | `GET /api/projects/{pid}/samples/{sid}/knowledge-draft` | `200`，含 `skillMarkdown`、`entryMeta` | ☐ |
| A.7 | Promote | 填写标题/分类/风格 → **加入知识库** | 提示成功 | ☐ |
| A.8 | 全局库文件 | 文件系统 | `storage/knowledge/{categorySlug}/{entryId}/` 三文件齐全 | ☐ |
| A.9 | 全局库 API | `GET /api/knowledge/entries` | 含新条目，`status=published` | ☐ |
| A.10 | Skill 正文 | `GET /api/knowledge/entries/{entryId}/skill` | 返回 Markdown 正文 | ☐ |
| A.11 | Promote 幂等 | 同一 sample 再次 promote | 返回 **相同 entryId**，全局库不重复条目 | ☐ |

**记录：** sampleId = `________`　entryId = `________`　categorySlug = `________`

---

### 场景 B：仅 Brief → 自动 recommend + bind → 生成（无样例项目）

**目的：** 验收「填 Brief 即可开跑」；验证 auto-apply knowledge structure。

| # | 步骤 | UI / API | 预期结果 | ✓ |
|---|------|----------|----------|---|
| B.1 | **新建项目**（勿上传样例） | `/projects` → 新建 | 空项目工作台 | ☐ |
| B.2 | 填写 Brief（主题 A） | 录入 → 创作 Brief → 保存 | 保存成功 | ☐ |
| B.3 | 推荐知识面板 | 录入区 **推荐知识** | 显示 **「已自动选用：{title}」** + 匹配理由 tags | ☐ |
| B.4 | Selection API | `GET .../knowledge/selection` | `primaryEntryId` = 场景 A 的 entryId，`mode=auto` | ☐ |
| B.5 | Recommend API | `POST .../knowledge/recommend` | 返回 `candidates` Top-K + `suggestedPrimaryId`；**不重复 bind**（selection 不变） | ☐ |
| B.6 | 开始生成计划 | **开始生成计划** | `201`，任务进入进度 | ☐ |
| B.7 | Samples 列表 | `GET .../samples` 或 UI | 存在 `sourceKind=knowledge` 的 analyzed 样例 | ☐ |
| B.8 | 生成完成 | 缺口 / 结构槽 / 结果 | GapReport、GenerationPlan 正常产出 | ☐ |
| B.9 | Brief 不匹配对照 | 新建项目 + Brief 主题 B | 仍 bind Top-1，但 score/reasons 不同（可接受） | ☐ |

**记录：** 项目 ID = `________`　knowledge sampleId = `________`

---

### 场景 C：有真实样例 + knowledge — 结构权威不覆盖（验收 #6）

**目的：** 验证审查修复项：真实样例 structure 优先；禁止 knowledge 覆盖。

**前置：** 使用场景 A 的项目（已有 analyzed 真实样例 + 已 promote 条目）。

| # | 步骤 | UI / API | 预期结果 | ✓ |
|---|------|----------|----------|---|
| C.1 | 保存 Brief（主题 A） | 录入 | 推荐面板显示已选用 knowledge（**reference**） | ☐ |
| C.2 | 手动应用结构 | **应用为项目结构** | **失败** 或 400，提示 knowledge 仅作参考 | ☐ |
| C.3 | structure-from-knowledge API | `POST .../structure-from-knowledge`<br>`{"entryId":"...","applyStructure":true}` | `400`，含 `reference only` | ☐ |
| C.4 | 开始生成 | 开始生成计划 | 成功 | ☐ |
| C.5 | 结构槽内容 | 结构槽面板 | 与 **真实样例** VideoStructure 一致（非 knowledge JSON） | ☐ |
| C.6 | DB 优先级 | 若 knowledge sample 的 `updated_at` 更新 | `get_latest_sample_structure` 仍返回 **真实样例** structure | ☐ |

---

### 场景 D：用户 override 与恢复自动

| # | 步骤 | UI / API | 预期结果 | ✓ |
|---|------|----------|----------|---|
| D.1 | 准备 ≥2 条 published 条目 | 重复场景 A 或第二项目 promote | 全局库 ≥2 条 | ☐ |
| D.2 | 展开「查看其他推荐」 | 推荐知识面板 | 候选列表 + 分数 + 理由 | ☐ |
| D.3 | 选用非 Top-1 | 点击 **选用** | 显示 **「已手动选用」**，`mode=user_override` | ☐ |
| D.4 | 再次保存 Brief | 修改 topic 后保存 | **primaryEntryId 不变**，仍为手动选用条目 | ☐ |
| D.5 | 恢复自动 | **恢复自动选用** | 回到 Top-1，`mode=auto` | ☐ |
| D.6 | Reset API | `POST .../knowledge/selection/reset` | 同 D.5 | ☐ |

---

### 场景 E：知识库 Tab 与全局浏览（Power User）

| # | 步骤 | UI | 预期结果 | ✓ |
|---|------|-----|----------|---|
| E.1 | 打开 **知识库** Tab | 工作台导航 | 推荐面板 + 全局列表 +（有 sample 时）草稿区 | ☐ |
| E.2 | 搜索 | 知识库搜索框输入分类/标题关键词 | 列表过滤正确 | ☐ |
| E.3 | 打开条目 | 点击某条目 | 右侧 Markdown 预览 | ☐ |
| E.4 | 选用此条目 | **选用此条目** | selection 更新，录入区同步 | ☐ |
| E.5 | 刷新页面 | F5 | selection / 推荐状态从 API 恢复 | ☐ |

---

### 场景 F：生成链路 Agent 渐进披露（可选 / Live 推荐）

**目的：** 验证 `knowledgeContext` 注入与 L1/L2 升级。

| # | 步骤 | 操作 | 预期结果 | ✓ |
|---|------|------|----------|---|
| F.1 | 确保项目已 bind knowledge | 场景 B 或 D | selection 有 primaryEntryId | ☐ |
| F.2 | 跑完整生成 | 开始生成计划 → 等待完成 | 无 knowledge 相关 hard fail | ☐ |
| F.3 | Agent Runs | 结果页 → Agent Runs 抽屉 | 存在 `slot_mapper` / `storyboard_writer` / `gap_planner` run | ☐ |
| F.4 | 检查 input_summary | agent run 日志或 SQLite `agent_runs` | inputs 含 `knowledgeContext` 或等价 keys | ☐ |
| F.5 | L2 触发（弱匹配多） | 使用素材缺口较大的 Brief/资产 | weak slots ≥2 时 primary content 为 **完整 skill MD**（含 `## 适用场景` 等标题） | ☐ |
| F.6 | Live selector（可选） | `VIDEOMAKER_FIXTURE_MODE=false` + 配 text 模型 | recommend 可能 subprocess rerank；失败时 fallback stage A 分数 | ☐ |

---

### 场景 G：generation-plan 携带 Brief（审查修复项）

| # | 步骤 | API / UI | 预期结果 | ✓ |
|---|------|----------|----------|---|
| G.1 | 项目已有旧 Brief（主题 B） | — | — | ☐ |
| G.2 | 一次请求带新 Brief 生成 | `POST .../generation-plan`<br>body: `{ "brief": { "topic": "电商带货", ... } }` | `201`；selection 按 **新 brief** 匹配电商 entry | ☐ |
| G.3 | 顺序验证 | 对比仅 save_brief 后再 generation-plan | 与 G.2 选用结果一致 | ☐ |

---

## 4. 存储与数据库核对清单

完成场景 A/B 后，逐项勾选：

```text
storage/
├── projects/{projectId}/
│   ├── samples/.../analysis/          # 样例分析产物（已有）
│   └── knowledge/drafts/{sampleId}/   # ☐ draft 三文件
└── knowledge/{categorySlug}/{entryId}/ # ☐ published 三文件
```

**SQLite（`services/api/storage/videomaker.sqlite3` 或 env 指定路径）：**

```sql
-- 已发布条目
SELECT id, title, category, slot_pattern, status FROM knowledge_entries;

-- 项目选用
SELECT project_id, primary_entry_id, mode, applied_as_structure
FROM project_knowledge_selection;

-- knowledge 样例（场景 B）
SELECT id, source_kind, status FROM samples WHERE project_id = '...';
```

| 检查项 | 预期 | ✓ |
|--------|------|---|
| `knowledge_entries.skill_md_uri` 为相对 storage 路径 | 非绝对路径、无 `..` | ☐ |
| promote 后 draft 仍保留 | 项目 draft 目录未删除（可再 promote 幂等） | ☐ |
| 无 git 跟踪的 runtime 产物 | `storage/` 仍在 .gitignore | ☐ |

---

## 5. API 快速探针（curl / PowerShell）

将 `{pid}`、`{sid}`、`{eid}` 替换为实际 ID：

```powershell
$base = "http://localhost:8000"

# 全局库
Invoke-RestMethod "$base/api/knowledge/entries"

# Draft
Invoke-RestMethod "$base/api/projects/{pid}/samples/{sid}/knowledge-draft"

# 推荐（不 auto-bind）
Invoke-RestMethod -Method Post "$base/api/projects/{pid}/knowledge/recommend"

# 当前选用
Invoke-RestMethod "$base/api/projects/{pid}/knowledge/selection"

# Skill 正文
Invoke-RestMethod "$base/api/knowledge/entries/{eid}/skill"
```

---

## 6. 失败判定与排查

| 现象 | 可能原因 | 排查 |
|------|----------|------|
| 无知识草稿卡片 | draft 未生成或 analysis 未完成 | 查 progress stage；看 `drafts/{sampleId}/structure-skill.md` |
| Promote 404 | draft 缺失 | 确认 A.5 文件存在 |
| 生成报「无 structure」 | ensure_selection 未跑或库空 | 先 promote；查 `project_knowledge_selection` |
| 生成用了 knowledge 结构而非样例 | 回归 bug | 查 samples 两条 structure；跑 `test_knowledge_routes` C 类用例 |
| 推荐面板一直加载失败 | API 未启 / CORS | Network 面板；`/health` |
| `rendering_knowledge_draft` 未出现 | 阶段被跳过或极快 | 查 task events SSE；Worker 日志 |
| Agent 无 knowledgeContext | selection 为空 | 查 bind 状态与 `context_resolver` |

**日志位置：**

- API / Worker：`services/api` 终端 stdout
- 任务事件：`GET /api/tasks/{taskId}/events`

---

## 7. 签核表

| 场景 | 描述 | 执行人 | 日期 | 结果 |
|------|------|--------|------|------|
| 0 | 健康检查 | | | ☐ Pass ☐ Fail |
| A | 样例 → draft → promote | | | ☐ Pass ☐ Fail |
| B | Brief-only auto-bind + 生成 | | | ☐ Pass ☐ Fail |
| C | 真实样例不被 knowledge 覆盖 | | | ☐ Pass ☐ Fail |
| D | override / reset | | | ☐ Pass ☐ Fail |
| E | 知识库 Tab / 浏览 | | | ☐ Pass ☐ Fail |
| F | Agent 渐进披露（可选） | | | ☐ Pass ☐ Fail ☐ N/A |
| G | generation-plan 带 Brief | | | ☐ Pass ☐ Fail |
| §4 | 存储 / DB 核对 | | | ☐ Pass ☐ Fail |

**整体结论：** ☐ 通过 E2E，可进入下一阶段 ☐ 阻塞项见备注

**备注：**

```text
（记录失败步骤、截图路径、taskId、entryId）
```

---

## 8. 与自动化测试的关系

| 层级 | 已覆盖（CI 可跑） | E2E 手动独有 |
|------|-------------------|--------------|
| shared/worker/api 单测 | 推荐打分、draft 落盘、L1/L2、路由规则 | — |
| Web 单测 | Workbench mock，不报错 | 真实 UI 交互、Markdown 渲染 |
| 本清单 | — | 全链路时序、文件落盘目检、Agent Runs 目检、Live LLM |

**建议：** 每次发版前至少完成 **场景 A + B + C**；Live 环境加 **F**。

---

## 9. 参考文档

- 实现计划：`docs/superpowers/plans/2026-06-03-knowledge-deposition-plan.md`
- 存储与 API：`AGENTS.md` → Storage Rules / Knowledge API
- P0 通用 demo：`docs/demos/p0-demo-checklist.md`
