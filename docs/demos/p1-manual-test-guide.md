# P1 手动测试指南

本文档面向 **P1 全部功能已合并** 后的端到端手动验收。P0 底座检查仍适用，见 [`p0-demo-checklist.md`](./p0-demo-checklist.md) 与 [`p0-demo-case.md`](./p0-demo-case.md)。

**快速勾选版**：[`p1-demo-checklist.md`](./p1-demo-checklist.md)

---

## 0. 测试策略

### 两档测试路径

| 路径 | 适用场景 | 关键配置 |
| --- | --- | --- |
| **Fixture 模式** | 无模型 Key、CI 回归、UI/流程冒烟 | `VIDEOMAKER_FIXTURE_MODE=true`（API 进程环境） |
| **Live 模式** | 真实 P1 演示、模型/AIGC 验收 | `VIDEOMAKER_FIXTURE_MODE=false` + 各 `*_API_*` 环境变量 |

Fixture 模式会返回预录 Agent JSON，**不调用外部 LLM/AIGC**，但可验证任务流、SSE、双变体、改片 API、artifact 注册与大部分 UI。

Live 模式是 P1 **最终验收** 所必需的路径。

### 推荐执行顺序

```text
预检（health + model-gateway）
  → P0 底座冒烟（上传 / SSE / 刷新恢复）
  → 样例 LLM 结构 + evidence
  → Brief + 素材理解
  → 双变体生成（进度 / 对比 / AIGC / HF / TTS）
  → NL 改片
  → Retry checkpoint
  → 异常场景（可选）
  → API / 磁盘抽检
```

预计耗时：**Fixture 约 30–45 分钟**；**Live 约 1–2 小时**（取决于视频生成 API 延迟）。

---

## 1. 环境准备

### 1.1 前置依赖

- Python 虚拟环境：`services/api/.venv`（`run-dev.ps1` 会检查；已在 `.gitignore` 忽略）
- Node.js：`apps/web` 可 `npm install`
- 可选但 Live 演示强烈建议：
  - **HyperFrames CLI**（`npx hyperframes doctor` 通过）
  - **FFmpeg**、**Whisper**（样例分析 perception 层）
  - 外部模型 API Key（text / vision / image / tts / video）

### 1.2 启动服务

**终端 1 — API + Worker（推荐脚本）**

```powershell
cd d:\VideoMaker\services\api
# 在此终端设置环境变量（见 §1.3），然后：
.\run-dev.ps1
```

**终端 2 — Web**

```powershell
cd d:\VideoMaker\apps\web
Copy-Item .env.example .env.local   # 首次
# 编辑 .env.local：
#   VIDEOMAKER_API_URL=http://127.0.0.1:8000
#   VIDEOMAKER_USE_FIXTURE_FALLBACK=false
npm run dev
```

浏览器打开：`http://localhost:3000/projects`

> 若使用 fixture fallback（仅 API 不可达时）：`VIDEOMAKER_USE_FIXTURE_FALLBACK=true`。  
> **P1 验收时应设为 `false`**，确保走真实 BFF → API。

### 1.3 Live 模式配置

**A. 运行模式（环境变量，API 启动终端）**

```powershell
$env:VIDEOMAKER_FIXTURE_MODE = "false"
$env:VIDEOMAKER_VIDEO_GEN_MAX_PER_SLOT = "1"
# Optional cap across all visual slots in one generation:
# $env:VIDEOMAKER_VIDEO_GEN_MAX_SLOTS = "3"
$env:VIDEOMAKER_DEFAULT_VARIANTS = "high_click,high_conversion"
```

**B. 模型凭据（工作台 UI → SQLite）**

1. 打开任意项目工作台，找到 **模型服务** 面板。
2. 为 **文本**、**生图**（至少）填写 Base URL、Model、API Key，点击 **保存配置**。
3. 可选：配置视觉 / 配音 / 生视频（生视频需填写 Base URL；视觉未单独配置 Key 时回退文本）。

凭据写入 `storage/videomaker.sqlite3` 的 `model_gateway_providers` 表；密钥加密文件：`storage/global/model-gateway.key`（勿提交 git）。

也可用 API 写入：

```http
PUT /api/settings/model-gateway
Content-Type: application/json

{
  "providers": {
    "text": { "baseUrl": "https://api.openai.com/v1", "apiKey": "sk-...", "model": "gpt-4o-mini" },
    "image": { "baseUrl": "https://api.openai.com/v1", "apiKey": "sk-...", "model": "dall-e-3" }
  }
}
```

**Fixture 冒烟**只需：

```powershell
$env:VIDEOMAKER_FIXTURE_MODE = "true"
```

（无需在 UI 填写模型 Key。）

### 1.4 启动预检

| 检查项 | 命令 / 操作 | 期望 |
| --- | --- | --- |
| API 健康 | `curl http://127.0.0.1:8000/health` | `{"ok":true}` |
| Gateway 状态 | `curl http://127.0.0.1:8000/api/settings/model-gateway` | JSON 含 `providers.text/image/...`，**不含 API Key** |
| Web 可达 | 打开 `/projects` | 项目列表或空态正常 |
| Gateway 面板 | 工作台 **模型服务** | Live：`fixtureMode: false` 且 text/image「已配置」；Fixture：显示 Fixture 模式徽章 |

---

## 2. 测试数据

### 2.1 样例视频

参考 [`p0-demo-case.md`](./p0-demo-case.md)：

- 时长 **15–60 秒** 竖屏短视频
- 结构清晰：**hook → 卖点/证明 → CTA**
- 含口播更佳（便于 ASR evidence）

准备 **本地 MP4** 一条；可选再测 **URL 导入**（需 yt-dlp + cookies 若平台需登录）。

### 2.2 产品 Brief（示例）

| 字段 | 示例值 |
| --- | --- |
| topic | 便携榨汁杯 |
| productName | FreshBlend Mini |
| sellingPoints | 30 秒出汁、易清洗、USB 充电 |
| mustMention | 食品级材质 |
| targetAudience | 上班族、健身人群 |

### 2.3 用户素材

上传 **2–3 项** 混合素材：

- 1 张产品图（PNG/JPG）
- 1 段短 clip（可选）
- 1 段说明文字 / caption

用于验证 `visualTags`、`suggestedSegmentRoles`（hook / mid / cta 推荐）。

---

## 3. Phase A — P0 底座回归（必做）

在 Live 或 Fixture 下均需通过。

| 步骤 | 操作 | 期望 |
| --- | --- | --- |
| A1 | `/projects` → 新建项目 | 跳转 `/projects/{id}` |
| A2 | **录入** 面板：本地上传样例 | 文件出现在 `storage/projects/{projectId}/samples/` |
| A3 | 点击 **开始样例分析** | **进度** 面板出现 taskId；阶段含上传、转写、镜头、**结构拆解 / 运行 AI 分析** |
| A4 | 分析进行中 **刷新页面** | 进度通过 SSE 或 polling 恢复；不丢 taskId |
| A5 | 保存 Brief + 上传素材 | API 持久化；刷新后仍在 |

---

## 4. Phase B — ModelGateway 与 Web 状态

| 步骤 | 操作 | 期望 |
| --- | --- | --- |
| B1 | 工作台顶部查看 Gateway 面板 | 五类 provider：文本、视觉、配音、生图、生视频 |
| B2 | Live：仅配置 TEXT+IMAGE | 文本/生图绿色；未配项 amber「未配置」+ env 提示 |
| B3 | `GET /api/settings/model-gateway` | 响应无 secret；含 `fixtureMode` |
| B4 | 未配 TEXT 时启动分析（Live） | 任务失败；UI 显示 **「模型服务未配置」**（`gateway_not_configured`） |

---

## 5. Phase C — LLM 样例结构 + Evidence

| 步骤 | 操作 | 期望 |
| --- | --- | --- |
| C1 | 分析完成后打开 **样例分析** | metadata / transcript / shots 可见 |
| C2 | 打开 **结构槽** | `VideoStructure`：narrative、rhythm、packaging、slots |
| C3 | 结构证据区（StructureEvidencePanel） | 各 narrative 段显示 **字幕摘录**、**关键帧说明**、关联 slot |
| C4 | 点击 evidence 关联 slot | 槽位板高亮对应 slot（联动） |
| C5 | API 抽检 | `GET /api/samples/{sampleId}/structure` 含 `evidence[]`，`source` 为 `asr` / `keyframe` 等 |
| C6 | 磁盘 | `storage/projects/{projectId}/samples/{sampleId}/analysis/structure.json` 存在 |

**失败语义（P1 锁定）**：LLM 校验失败应 **直接 failed**，UI 提示 **「AI 输出格式异常」**，**不应** 回退到 P0 规则 pipeline。

---

## 6. Phase D — 素材理解（ContentStrategist）

| 步骤 | 操作 | 期望 |
| --- | --- | --- |
| D1 | **录入** → 确认已保存 Brief + 素材 | — |
| D2 | 开始生成后观察 **分析素材** 阶段 | stage 标签：**分析素材** |
| D3 | 生成完成后查看 gap/结构相关 UI 或 `asset-inventory.json` | 每项 asset 含 `visualTags` |
| D4 | 同上 | 含 `suggestedSegmentRoles`（如 hook / mid / cta 时刻推荐） |

API：`GET /api/projects/{id}/assets` 返回元数据；完整 inventory 在 generation 产物目录。

---

## 7. Phase E — 槽位匹配 + 缺口规划

| 步骤 | 操作 | 期望 |
| --- | --- | --- |
| E1 | **结构槽** → StructureSlotBoard | 每 slot 显示语义 **matchReason**（非空、可读） |
| E2 | **缺口** → GapReportView | matched / weak / missing 分区 |
| E3 | 弱/缺 slot | 每项显示选定 **provider**：`hyperframes_material`、`image_generation`、`video_generation`、`tts`、`asset_reuse` 之一 |
| E4 | Provider badge | `GeneratedAssetBadge` 显示来源标签 |
| E5 | 磁盘 | `generations/{generationId}/gap-report.json` |

---

## 8. Phase F — 双变体生成

| 步骤 | 操作 | 期望 |
| --- | --- | --- |
| F1 | **录入** 底部 **生成变体**（VariantPicker） | 默认勾选 **高点击版** + **高转化版** |
| F2 | 取消一个变体后生成 | 仅启动所选 variant 的 task |
| F3 | 点击 **开始生成视频** | 返回 **2 个** generationId + taskId（默认全选时） |
| F4 | **进度** 面板 | **MultiTaskProgressPanel** 并排跟踪两个任务 |
| F5 | 阶段标签 | 含 **槽位匹配、缺口规划、生成分镜、构建时间线**；素材阶段含 **AI 生图 / 生视频 / 合成配音 / 渲染包装片段** |
| F6 | SSE 断连测试（可选） | 关 DevTools 网络再恢复；polling 兜底仍更新 |
| F7 | 完成后 **结果** | **VariantTabs** 切换 high_click / high_conversion |
| F8 | VariantCompareView | 并排对比 storyboard / timeline 差异 |
| F9 | 两变体内容 | 高点击 hook 更强/节奏更快；高转化卖点/CTA 更重（允许 LLM 波动，但方向应可感知） |
| F10 | 刷新页面 | `GET /api/projects/{id}/generations/latest` 恢复两变体结果 |

---

## 9. Phase G — AIGC / HyperFrames / TTS

| 步骤 | 操作 | 期望 |
| --- | --- | --- |
| G1 | 进度面板 **TaskArtifactPreview** | 素材阶段增量展示 artifact（image/audio/video/json） |
| G2 | **生视频配额** | 每个视觉槽位默认 **最多 1 次** 成功 `video_generation`（`VIDEOMAKER_VIDEO_GEN_MAX_PER_SLOT`）；同一槽位第二次应 `video_quota_exceeded`；`generated/slot*.mp4` 应为真实动效（DashScope Wan），而非静图 `asset_reuse` |
| G3 | 时间线 / 结果 | 至少 **1 段 AI 生成视频** clip（Live）或 fixture 占位 artifact |
| G4 | HyperFrames 包装 | timeline 或 gap 中含 **hyperframes_material** 产物；benefit card / 包装片段 |
| G5 | 打开 HF preview | `storage/.../generations/{id}/render/preview.html` 可访问（或 UI 外链） |
| G6 | TTS / 字幕 | `generated/slot*.wav` 非空；`composition/timeline.json` 含 voiceover + text 字幕轨；最终 `output.mp4` **可听到旁白、可见底部分镜字幕**（Live）；fixture 模式至少存在 `.wav` artifact |
| G7 | HF CLI 缺失（可选） | 任务可失败或跳过并显示 **HyperFrames 未安装**（`hyperframes_missing`） |

磁盘关键路径：

```text
storage/projects/{projectId}/generations/{generationId}/
  asset-inventory.json
  gap-report.json
  generation-plan.json
  render-timeline.json
  materials/          # AIGC / HF 片段 + slot*.wav 旁白
  generated/slot*.wav # TTS 按槽产物
  render/preview.html
  render/output.mp4   # 含 voiceover + 字幕混流
  agent-runs/         # 可选
  checkpoint.json
```

---

## 10. Phase H — 自然语言改片（NL Revise）

**前置**：某一变体 generation **已成功**（status succeeded）。

| 步骤 | 操作 | 期望 |
| --- | --- | --- |
| H1 | **结果** 面板 **自然语言改片** | ReviseInputBar 可见 |
| H2 | 输入：`开头更抓人，字幕少一点` → **提交改片** | 新 task；阶段 **理解改片指令** → **应用改片** |
| H3 | 新 generation | 继承源 variant；产生新 generationId |
| H4 | EditIntentList | 展示解析出的 intent 条目（如 hook_strength、subtitle_density） |
| H5 | TimelineDiffSummary | 与源 generation 的 diff 摘要可见 |
| H6 | API | `POST /api/generations/{id}/revise` body: `{"instruction":"..."}` → 202 + 新 taskId |
| H7 | 磁盘 | `edit-intent.json` 落盘 |

**边界**：

- 源 generation 未成功 → API 400
- 空 instruction → 前端禁用提交

---

## 11. Phase I — Retry / Checkpoint

| 步骤 | 操作 | 期望 |
| --- | --- | --- |
| I1 | 任选进行中任务 **刷新** | 同一 taskId 继续，不新建 analyze task |
| I2 | 模拟失败（如 Live 下暂时去掉 KEY） | 任务 failed + 结构化 error |
| I3 | 点击 **重试生成计划** / **重试样例分析** / **重试改片** | `POST /api/tasks/{taskId}/retry`，**同一 taskId** |
| I4 | 恢复配置后重试 | 从 `checkpoint.json` **跳过已完成 stage**；仍走 **LLM Agent 路径**（非规则 fallback） |
| I5 | 日志 | 不应出现 `structure_pipeline` 等 P0 规则语义回退 |

---

## 12. Phase J — 可观测性

| 步骤 | 操作 | 期望 |
| --- | --- | --- |
| J1 | **结果** → **查看 AI 调用链** | AgentRunsDrawer 列出 agent run logs |
| J2 | `GET /api/generations/{id}/agent-runs` | `{ runs: [...] }` 含 agent 名、耗时、status |
| J3 | 磁盘 | `generations/{id}/agent-runs/*.json` 可选存在 |

---

## 13. 异常与边界场景（建议）

| 场景 | 操作 | 期望 |
| --- | --- | --- |
| 无结构就生成 | 跳过样例分析直接 **开始生成视频** | API 400 + 明确提示先分析 |
| 无 Key（Live） | 启动分析/生成 | failed + gateway_not_configured |
| 视频配额 | 同一 slot 触发第 2 次生视频 | video_quota_exceeded |
| LLM schema 失败 | （难模拟） | LLMValidationError + 可重试 |
| 仅选一个变体 | VariantPicker 只留 high_click | 只 1 个 task |
| Fixture fallback | API 关闭 + `VIDEOMAKER_USE_FIXTURE_FALLBACK=true` | 前端演示数据 banner；**不计入 P1 Live 验收** |

---

## 14. API 抽检命令

将 `{projectId}`、`{sampleId}`、`{generationId}`、`{taskId}` 替换为实际值。

```powershell
# 健康与 Gateway
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/api/settings/model-gateway

# 项目与样例
curl http://127.0.0.1:8000/api/projects/{projectId}
curl http://127.0.0.1:8000/api/projects/{projectId}/samples/active
curl http://127.0.0.1:8000/api/samples/{sampleId}/structure

# 双变体生成
curl -X POST http://127.0.0.1:8000/api/projects/{projectId}/generation-plan `
  -H "Content-Type: application/json" `
  -d "{\"variants\":[\"high_click\",\"high_conversion\"]}"

# 最新结果（刷新恢复）
curl http://127.0.0.1:8000/api/projects/{projectId}/generations/latest

# 单 generation 详情
curl http://127.0.0.1:8000/api/generations/{generationId}

# 改片
curl -X POST http://127.0.0.1:8000/api/generations/{generationId}/revise `
  -H "Content-Type: application/json" `
  -d "{\"instruction\":\"开头更抓人，字幕少一点\"}"

# Agent runs
curl http://127.0.0.1:8000/api/generations/{generationId}/agent-runs

# 任务进度
curl http://127.0.0.1:8000/api/tasks/{taskId}
curl "http://127.0.0.1:8000/api/tasks/{taskId}/events?once=true"

# Retry
curl -X POST http://127.0.0.1:8000/api/tasks/{taskId}/retry
```

---

## 15. 自动化回归（合并前门禁）

与 integration 分支 gate 一致：

```powershell
cd packages/contracts
npm run check
npm run validate:schemas

cd ../../services/api
python -m pytest
python -m compileall app

cd ../worker
python -m pytest
python -m compileall app

cd ../../apps/web
npm run typecheck
npm run test
```

手动验收 **不能替代** 上述自动化测试；建议先绿再跑 Live 演示。

---

## 16. P1 验收结论标准

以下 **全部满足** 方可认定 P1 手动验收通过（Live 路径）：

1. LLM 样例结构 + **evidence** 可点击/可核对  
2. 素材 **visualTags** + **suggestedSegmentRoles**  
3. Slot **matchReason** + Gap **provider** 可解释  
4. **高点击 / 高转化** 两变体并排对比  
5. **1 次** AI 生视频 + HyperFrames 包装片段 + **TTS 可听**  
6. NL 改片产生 **EditIntent + diff**  
7. Retry **同 taskId**、checkpoint 恢复、**无规则语义 fallback**  
8. Web：Gateway 状态、P1 中文 stage、多 task 进度、artifact 预览  

---

## 17. 常见问题

| 现象 | 排查 |
| --- | --- |
| 工作台显示 fixture 数据 | `VIDEOMAKER_USE_FIXTURE_FALLBACK` 是否为 true；API 是否启动 |
| 分析一直卡在转写 | Whisper 模型下载；可设 `HF_ENDPOINT` 镜像 |
| 生成无 AIGC 产物 | 检查 IMAGE/TTS/VIDEO env；Fixture 模式下 artifact 可能为占位 |
| HyperFrames 失败 | `npx hyperframes doctor`；PATH 中是否有 CLI |
| 改片按钮不可用 | 需先选中 **已成功** 的 generation 结果 tab |
| 两变体只出一个 | VariantPicker 是否只选了一个；查看 generation-plan API 响应 |
