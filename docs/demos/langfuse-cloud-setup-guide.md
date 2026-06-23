# Langfuse Cloud 开通与 VideoMaker 对接指南

本指南帮助你在 **Langfuse Cloud（免费 Hobby 档）** 上开通项目，并把 VideoMaker 的样本分析 / 视频生成链路接入观测。代码侧已内置 `LangfuseSink`，只需配置环境与安装依赖。

## 1. 架构说明

```text
工作台 / API
    └── worker 子进程 (run_p0_task.py)
            └── build_observability_sink()
                    ├── LocalFileSink  → storage/projects/{projectId}/logs/  （默认始终写入）
                    └── LangfuseSink   → Langfuse Cloud                    （需显式开启）
```

- **不会自动开启 Langfuse**；未配置时仅有本地 `model-calls` / `agent-runs` / `tool-runs`。
- Worker 继承 **启动 API 时** 的环境变量；改 env 后需 **重启 API**。
- 任务结束时 worker 会 `flush_observability()`，Langfuse UI 通常在 **30 秒内**可见。

## 2. 开通 Langfuse Cloud（约 5 分钟）

1. 打开 [https://cloud.langfuse.com](https://cloud.langfuse.com) 注册账号（Hobby **免费**，无需信用卡）。
2. 创建 **Organization** → **Project**（建议命名 `videomaker-dev`）。
3. 进入 Project → **Settings** → **API Keys** → **Create new API keys**。
4. 记录：
   - **Public Key**：`pk-lf-...`
   - **Secret Key**：`sk-lf-...`（只显示一次，请妥善保存）
5. 确认 **数据区域** 与 `LANGFUSE_BASE_URL` 一致（登录 URL 决定区域）：

| 区域 | 登录 / Base URL |
|------|-----------------|
| EU（默认） | `https://cloud.langfuse.com` |
| US | `https://us.cloud.langfuse.com` |
| Japan | `https://jp.cloud.langfuse.com` |
| HIPAA US | `https://hipaa.cloud.langfuse.com` |

未设置 `LANGFUSE_BASE_URL` 时 SDK 默认连 **EU**；若项目在 US/Japan 等区域，必须在 `langfuse.env` 中显式设置，否则会出现 401。验证脚本在未配置时会 **自动探测** 可用区域并提示应写入的 URL。

### Hobby 免费档限制（一般足够 E2E）

| 项 | 额度 |
|----|------|
| 用量 | 约 50,000 units / 月 |
| 数据保留 | 30 天 |
| 用户数 | 2 |

超出 Hobby 硬上限后新 trace 可能不再接收；日常 E2E 通常远低于额度。

## 3. VideoMaker 环境配置

### 3.1 安装 Langfuse SDK（关键）

Worker 在 **API 子进程**里运行，Python 解析顺序为：

1. `services/worker/.venv/Scripts/python.exe`
2. 否则 `services/api/.venv/Scripts/python.exe`（`run-dev.ps1` 常见情况）
3. 否则系统 Python

`verify-langfuse.ps1` 若落到 **conda/系统 Python**，连通性测试可能成功，但 **E2E 生成仍不会上报 Langfuse**——因为实际 worker 用的是 `services/api/.venv`，其中默认 **未安装** `langfuse`。

推荐做法（任选其一）：

```powershell
# A. 由 run-dev.ps1 自动安装（LANGFUSE_ENABLED=true 时）
cd D:\VideoMaker\services\api
.\run-dev.ps1

# B. 手动安装到 API worker Python
cd D:\VideoMaker\services\api
.\.venv\Scripts\pip install "langfuse>=4.0,<5"

# C. 或创建 worker 专用 venv
cd D:\VideoMaker\services\worker
uv venv .venv
.\.venv\Scripts\pip install -e ".[langfuse]"
```

验证时请使用 **与 worker 相同的 Python**：

```powershell
cd D:\VideoMaker\services\worker
.\scripts\verify-langfuse.ps1
```

脚本会优先使用 `services/api/.venv`，并在缺失时自动 `pip install langfuse`。

### 3.2 配置密钥（推荐：langfuse.env）

```powershell
cd D:\VideoMaker\services\api
copy langfuse.env.example langfuse.env
# 编辑 langfuse.env，填入 pk/sk，并设 LANGFUSE_ENABLED=true
```

`langfuse.env` 已加入 `.gitignore`，**勿提交密钥**。

`langfuse.env.example` 内容示例：

```env
LANGFUSE_ENABLED=true
LANGFUSE_PUBLIC_KEY=pk-lf-your-public-key
LANGFUSE_SECRET_KEY=sk-lf-your-secret-key
# Cloud 默认无需 LANGFUSE_BASE_URL / LANGFUSE_HOST；自托管时才取消注释：
# LANGFUSE_BASE_URL=https://your-langfuse.example.com
VIDEOMAKER_OBSERVABILITY_CAPTURE=full
```

### 3.3 验证连通性

在填入 `langfuse.env` 后：

```powershell
cd D:\VideoMaker\services\worker
.\scripts\verify-langfuse.ps1
```

或手动：

```powershell
cd D:\VideoMaker\services\api
Get-Content langfuse.env | ForEach-Object {
  if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
    Set-Item -Path "env:$($matches[1].Trim())" -Value $matches[2].Trim().Trim('"')
  }
}
cd ..\worker
.\.venv\Scripts\python.exe scripts\verify_langfuse.py
```

期望输出：`OK: Langfuse Cloud flush succeeded` 以及一行 `trace id: <32位hex>`。

在 Langfuse UI → **Tracing** 中按该 trace id 搜索，或查看最新 traces。

### 3.4 启动 API（自动加载 langfuse.env）

```powershell
cd D:\VideoMaker\services\api
.\run-dev.ps1
```

`run-dev.ps1` 会在存在 `services/api/langfuse.env` 时自动加载。另开终端启动 Web：

```powershell
cd D:\VideoMaker\apps\web
npm run dev
```

### 3.5 确认 Live 模式

E2E 不要用 fixture 模式：

```powershell
# 确保未设置，或显式关闭：
$env:VIDEOMAKER_FIXTURE_MODE = "false"
```

Model Gateway 已在工作台配置好 text/vision/image/video/tts provider。

## 4. 跑完整 E2E 并查看观测

### 4.1 推荐流程

1. 工作台创建项目 → 上传样例视频 → **分析样本**（记下 `task_id`）
2. 填写 brief / 素材 → **生成**（记下 `generation_id` 与各 variant 的 `task_id`）
3. 等待任务 `completed`（或失败）

### 4.2 Langfuse UI 中如何找 trace

打开 [cloud.langfuse.com](https://cloud.langfuse.com) → 你的 Project → **Tracing**。

| VideoMaker 概念 | Langfuse 字段 |
|-----------------|---------------|
| 任务 ID | **Session** = `taskId`；Trace ID = `task-{taskId}` |
| 项目 ID | **User** = `projectId` |
| 生成 ID | Trace **Metadata** → `generationId` |

**样本分析**与**视频生成**通常是 **不同的 task**，各对应一条 trace。

### 4.3 Trace 里能看到什么

**样本分析 task：**

- Agent span：`structure_analyst`、`segment_analyst`、`keyframe_batch_analyst` 等
- Generation：`chat_json` / vision 相关调用

**生成 task：**

- Agent span：`content_strategist`、`slot_mapper`、`gap_planner`、`storyboard_writer`、`material_author` 等
- Generation：`chat_json`、`chat_tools`（ReAct 分镜）、`image`、`video_submit`/`video_poll`、`tts`
- ACP 分镜（`VIDEOMAKER_COMPOSITION_AUTHOR_BACKEND=acp`）：`material_author:acp_session_start` / `acp_lint_gate` / `acp_session_end`（无 `chat_tools` model-call）

### 4.4 本地对照（不依赖 Langfuse）

```text
storage/projects/{projectId}/logs/
  model-calls/*.json
  agent-runs/*.json
  tool-runs/acp-*.json          # ACP 分镜
  composition-author/acp/{runId}/
```

API 查询：

```http
GET /api/tasks/{taskId}/model-calls?kind=chat
GET /api/generations/{generationId}/agent-runs
GET /api/generations/{generationId}/model-calls
```

工作台生成结果区有 **Agent Runs** 抽屉（按 `generationId`）；model-calls 暂无 UI，请用 API 或本地文件。

## 5. 环境变量速查

| 变量 | 必填 | 说明 |
|------|------|------|
| `LANGFUSE_ENABLED` | 是 | `true` / `1` / `yes` / `on` |
| `LANGFUSE_PUBLIC_KEY` | 是 | Cloud 项目 Public Key |
| `LANGFUSE_SECRET_KEY` | 是 | Cloud 项目 Secret Key |
| `LANGFUSE_HOST` | Cloud 否 | 仅自托管时设置 |
| `VIDEOMAKER_OBSERVABILITY_CAPTURE` | 否 | 默认 `full`；可改 `summary` 降低 Langfuse 体积 |
| `LANGFUSE_CAPTURE` | 否 | 单独限制 Langfuse 粒度，默认跟随 OBSERVABILITY_CAPTURE |
| `VIDEOMAKER_ACP_OBSERVABILITY_MAX_SESSION_UPDATES` | 否 | ACP `session_update` 条数上限，默认 `40` |

## 6. 故障排查

| 现象 | 处理 |
|------|------|
| Langfuse 无数据 | 确认 `langfuse.env` 存在且 `LANGFUSE_ENABLED=true`；重启 API；跑 `verify_langfuse.py` |
| `ImportError: langfuse` | `pip install -e ".[langfuse]"` in `services/worker` |
| 只有本地 logs、无 Cloud | 检查 Public/Secret Key；Hobby 额度是否用尽 |
| 任务成功但 UI 延迟 | 等待 30s；worker 结束时会 flush |
| 国内访问 Cloud 慢/失败 | 换网络或改 `summary`  capture；敏感数据可仅本地 logs 或未来自托管 |
| Fixture 模式无 LLM trace | 使用 live Model Gateway，关闭 `VIDEOMAKER_FIXTURE_MODE` |

## 7. 相关文档

- E2E 检查清单：[langfuse-observability-e2e-checklist.md](./langfuse-observability-e2e-checklist.md)
- ACP 分镜观测：[composition-acp-author-e2e-checklist.md](./composition-acp-author-e2e-checklist.md)
- 实现计划：[../superpowers/plans/2026-06-19-langfuse-observability-rollout-plan.md](../superpowers/plans/2026-06-19-langfuse-observability-rollout-plan.md)
