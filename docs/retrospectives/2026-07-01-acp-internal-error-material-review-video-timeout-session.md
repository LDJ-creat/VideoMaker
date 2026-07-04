# 会话复盘：Cursor ACP Internal error 与素材审核 video 超时

> **会话背景**：项目 `7bed327a-f272-4887-a294-938d30b98723`、改片 fork generation `21fbf28a-b79b-4876-b4d5-e43cbe6f10c4`、slot-2 单 slot 重生成；ACP 失败 fallback 空 benefit-card → 黑屏预览；素材审核 `text_only`；修复后 ACP 成功但 video review 读超时。  
> **文档用途**：后续出现 **ACP / composition author / material review** 问题时，按本文 **定位顺序 → 判据 → 修复** 执行，避免把 transient 错误当成并发或 lint 问题。

---

## 1. 问题总览

| # | 现象 | 根因 | 最终状态 |
|---|------|------|----------|
| 1 | slot-2 `material-spec.json` 为 `benefit-card` 空 params，预览黑屏 | Cursor ACP 首轮 `conn.prompt()` 抛 `Internal error`，无 session 重试；静默 fallback | 已修复（重试 + 日志 + 不依赖并发假设） |
| 2 | `material-reviews/slot-2/report.json` 中 `reviewInputs.mode: text_only` | Worker 子进程无 `ModelGatewayStore`（`VM_DATABASE_PATH` 未注入 + finalize 未传 store） | 已修复 |
| 3 | 审阅报「No slot preview content / finishBrief 未提供」 | 同上 text_only + `_build_author_payload` 未合并 `acp-author/task.json` | 已修复 |
| 4 | ACP 成功、预览正常，但审阅 `Material review failed: The read operation timed out` | `video_understanding` HTTP **read 超时默认 120s**，短 MP4 base64 上传 + 模型推理易超 | 已修复（默认 300s，可 env 调） |

---

## 2. 如何定位 ACP 失败（推荐顺序）

### Step 0：区分「ACP 作者失败」与「审核 / 渲染失败」

| 产物 | ACP 作者 | HF 渲染 | 素材审核 |
|------|----------|---------|----------|
| 关键路径 | `acp-author/{slotId}/task.json` | `generated/action-{slot}/composition/` | `material-reviews/{slotId}/report.json` |
| 成功标志 | `logs/.../acp/*/outcome.json` → `valid: true` + `tool_calls.jsonl` | `material-spec.json` 非空 fallback、有 `.lint-passed.json` | `reviewInputs.mode` 为 `video` 或 `frames` |

**空 benefit-card + 空 params** 几乎总是 **material_author 异常 → legacy fallback**，不是 lint 失败。

### Step 1：查 ACP outcome（项目级 trace）

```powershell
$project = "7bed327a-f272-4887-a294-938d30b98723"
$acpRoot = "D:\VideoMaker\services\api\storage\projects\$project\logs\composition-author\acp"
Get-ChildItem $acpRoot -Directory | ForEach-Object {
  $o = Join-Path $_.FullName "outcome.json"
  if (Test-Path $o) {
    $j = Get-Content $o -Raw | ConvertFrom-Json
    [PSCustomObject]@{ id=$_.Name; valid=$j.valid; error=($j.validationErrors -join ';'); ms=$j.totalLatencyMs; at=$j.recordedAt }
  }
} | Sort-Object at -Descending | Select-Object -First 10
```

**判据表：**

| outcome 特征 | 含义 | 下一步 |
|--------------|------|--------|
| `valid: false`, `Internal error`, **无** `tool_calls.jsonl` | Cursor agent 在 **首轮 prompt** 即崩，MCP 未启动 | Step 2 + 独立 smoke |
| `valid: false`, `acp_author_missing_material_spec` | Agent 跑了但未写 spec | 看 `tool_calls.jsonl` / Cursor 额度 |
| `valid: true`, 有 `tool_calls.jsonl` | ACP 正常 | 查 HF render / 审核，不是 ACP |
| `agentDiagnostics.agentStillRunning: true` | agent 子进程未回收 | 检查 zombie / 需 terminate |

本次失败 trace：`9798c990fe61` — `Internal error`，83s，**无 tool_calls**。

### Step 2：对比 scratch 与 session 元数据

```text
storage/projects/{projectId}/generations/{generationId}/acp-author/{slotId}/
  task.json          # 作者 brief（应有 compositionAuthorBrief）
  material-spec.json   # 成功时由 MCP 写入

logs/composition-author/acp/{runId}/
  session.json       # agentCommand、scratchDir、compositionTemplate、acpTimeoutSec
  prompt.json        # 完整 system+user（可对比 smoke）
  tool_calls.jsonl   # 有则 agent 曾调 MCP
  outcome.json
```

对比 **失败 vs 成功** 的 `session.json`：

- `compositionTemplate: true` → `acpTimeoutSec` 默认 **1800**
- smoke benefit-card → **600**
- 失败与成功 **命令相同** 时，更可能是 **transient Internal error**，不是配置差异

### Step 3：独立 smoke（剥离流水线）

```powershell
cd D:\VideoMaker\services\worker
$env:VIDEOMAKER_COMPOSITION_ACP_AGENT = "cursor"

# 快速 benefit-card
d:\VideoMaker\services\api\.venv\Scripts\python.exe scripts\verify_acp_cursor_smoke.py

# composition 模板（与 slot-2 同类）
d:\VideoMaker\services\api\.venv\Scripts\python.exe scripts\smoke_composition_acp_composition.py

# 用磁盘 task.json 复现指定 slot（可加 scripts/repro_slot2_acp.py）
```

| smoke 结果 | 流水线结果 | 结论 |
|------------|------------|------|
| 过 | 失败 | 集成层：env、store、retry、subprocess |
| 失败 | 失败 | Cursor CLI / 认证 / 额度 |
| 过 | 过（重试后） | transient，需 session retry |

本次：**smoke 与 repro 均过**，流水线首次 `Internal error` 为 **transient**。

### Step 4：Worker 日志

```powershell
Select-String -Path "D:\VideoMaker\services\api\storage\logs\worker.log" -Pattern "material_author failed|ACP prompt failed|Internal error|falling back to legacy"
```

修复后会看到：

```text
ACP prompt failed turn=1 scratch=... error=Internal error
ACP session attempt 1/2 failed (...); retrying new session
```

### Step 5：排除并发（仅当多 slot 同时 author）

单 slot 改片 **不必先怀疑并发**。多 slot 并行时才查：

- `VIDEOMAKER_MATERIAL_MAX_CONCURRENT_SLOTS`（默认 3）
- `VIDEOMAKER_MAX_CONCURRENT_GENERATIONS`（API，默认 2）

---

## 3. 根因详解：ACP Internal error

### 3.1 失败链

```text
hyperframes_material_provider._author_spec()
  → author_material_spec_via_acp()
    → spawn cursor agent.cmd --trust --model auto acp
    → conn.prompt(system+user)  # 首轮
      → RequestError / Internal error  (~83s)
  → except: LOGGER.warning("material_author failed ... falling back to legacy spec")
  → benefit-card params={} → HF 渲染黑底 → 审核 text_only / agent_failed
```

### 3.2 为何不是 lint / MCP / brief 问题

- 无 `tool_calls.jsonl` → MCP `write_material_spec` 从未调用
- `task.json` brief 完整（compositionAuthorBrief、renderPolicy 齐全）
- 同 payload 用 `repro_slot2_acp.py` 可成功 → brief 无误

### 3.3 为何不是并发

- 用户操作：**单 slot-2** material-slot-revise
- 成功重跑 trace `fa0a683e5756`：单 session、~73s、`template=composition`

---

## 4. 已实施修复（ACP + 审核）

| 模块 | 改动 |
|------|------|
| `composition/acp/author.py` | `Internal error` / `RequestError` 视为 session 级失败 → **自动重开 session**（`VIDEOMAKER_COMPOSITION_ACP_SESSION_RETRY`） |
| 同上 | `conn.prompt` 失败打 **ERROR** + agent diagnostics；session 结束 **terminate** agent 进程 |
| `hyperframes_material_provider.py` | **所有** HF slot 走 `_author_spec_with_retry`（原仅 finish action） |
| `pipeline_runner.py` | 子进程注入 **`VM_DATABASE_PATH`** |
| `generation_pipeline.py` / `material_review_finalize.py` | 显式构建并传递 **`ModelGatewayStore`** |
| `material_review.py` | `resolve_material_review_route` 打 **reason** 诊断日志 |
| `material_review_finalize.py` | 审核 payload 合并 **`acp-author/{slot}/task.json`** |
| `gateway/chat_timeout.py` | `video_understanding` 默认 **300s** read/write（原 120s） |

---

## 5. 素材审核 video 超时

### 5.1 现象

修复 ACP 后 slot-2 预览正常，但：

```json
"reviewInputs": { "mode": "video" },
"issues": ["Material review failed: The read operation timed out"]
```

说明 **路由已走 video**，失败在 **LLM HTTP 读响应**。

### 5.2 修复前超时配置

| 层级 | 配置 | 实际值 |
|------|------|--------|
| `OpenAICompatibleChatProvider` | 构造函数默认 | **120s**（connect/read/write 同一标量） |
| `ModelGateway._chat_provider` | 各 profile 共用 | 未区分 text / vision / video |
| 素材审核 | 无独立 timeout env | 继承 gateway 120s |

4.79s 预览 MP4 经 **base64 嵌入** 请求体，上游（如 DashScope 视频理解）处理常 **>120s**，触发 httpx `ReadTimeout` → 文案 `The read operation timed out`。

### 5.3 修复后推荐值

| Env | 默认 | 适用 |
|-----|------|------|
| `VIDEOMAKER_GATEWAY_VIDEO_UNDERSTANDING_TIMEOUT_SEC` | **300** | 素材审核 video、样本 direct multimodal、asset video |
| `VIDEOMAKER_GATEWAY_VISION_TIMEOUT_SEC` | **240** | 多帧 keyframe 审核 / vision profile |
| `VIDEOMAKER_GATEWAY_CHAT_TIMEOUT_SEC` | **120** | 纯文本 agent |

**为何选 300s：** 短 clip（≤30s、≤50MB，`MATERIAL_REVIEW_VIDEO_MAX_*`）在 base64 + 推理场景下，120s 偏紧；300s 覆盖 ~95% 单次审核，且仍远小于 ACP composition timeout（1800s）。若仍超时，可调到 **420–600**，或改走 vision 帧模式（`VIDEOMAKER_MATERIAL_REVIEW_MAX_FRAMES`）。

实现细节：

- multimodal profile 使用 **独立 httpx.Client**（避免与短 timeout 共享 client 冲突）
- `Timeout(connect=30, read=profile, write=max(120, profile))` — 大 body 上传需更长 write

---

## 6. 验证清单

### ACP 单 slot 重生成

```powershell
$body = '{"instruction":"重新生成 slot-2 金句字卡"}'
Invoke-RestMethod -Method POST -Uri "http://127.0.0.1:8000/api/generations/21fbf28a-b79b-4876-b4d5-e43cbe6f10c4/material-slots/slot-2/revise" -Body $body -ContentType "application/json"
# 轮询 task 至 awaiting_material_review
```

**通过：**

- `generated/action-slot-2/material-spec.json` → `"template": "composition"`
- 最新 `outcome.json` → `valid: true`，存在 `tool_calls.jsonl`
- UI 预览非黑屏

### 素材审核 video

- `report.json` → `reviewInputs.mode: "video"` 且无 read timeout
- worker.log → `material_review_route=video reason=video_understanding_ready`（或 vision fallback reason）

---

## 7. 关键路径速查

| 用途 | 路径 |
|------|------|
| ACP scratch | `storage/projects/{projectId}/generations/{generationId}/acp-author/{slotId}/` |
| ACP trace | `storage/projects/{projectId}/logs/composition-author/acp/{runId}/` |
| 素材审核报告 | `generations/{generationId}/material-reviews/{slotId}/report.json` |
| Worker 日志 | `services/api/storage/logs/worker.log` |
| 独立 smoke | `services/worker/scripts/verify_acp_cursor_smoke.py` |
| Composition smoke | `services/worker/scripts/smoke_composition_acp_composition.py` |
| Slot repro | `services/worker/scripts/repro_slot2_acp.py` |
| E2E checklist | `docs/demos/composition-acp-author-e2e-checklist.md` |

---

## 8. 可复述要点（面试 / 交接）

1. **先看 outcome.json 有没有 tool_calls** — 没有就是 prompt 阶段死，不是 lint。
2. **smoke 过、流水线不过** → env/store/retry，不是 Cursor 本体坏了。
3. **benefit-card 空 params** = silent fallback，要在日志里搜 `falling back to legacy spec`。
4. **text_only 不等于 ACP 失败** — 可能是 store 缺失；**video + read timeout** 才是审核 HTTP 超时。
5. **单 slot 改片默认排除并发**；只有多 slot 并行 author 才降 `MATERIAL_MAX_CONCURRENT_SLOTS`。

---

## 9. 相关 commit / 文件（本会话）

- `services/worker/app/composition/acp/author.py` — session retry、prompt 日志、进程 terminate
- `services/worker/app/providers/hyperframes_material_provider.py` — author retry
- `services/api/app/services/pipeline_runner.py` — `VM_DATABASE_PATH`
- `services/worker/app/pipelines/material_review.py` — route 诊断
- `services/worker/app/pipelines/material_review_finalize.py` — task.json merge
- `services/worker/app/gateway/chat_timeout.py` — profile 超时
- `services/worker/app/gateway/model_gateway.py` — 按 profile 注入 timeout

---

## 10. slot-5 长跑（2026-07-02 改片 fork）

### 判据

- `turnCount=1` 且 `tool_calls.jsonl` 行数 > 500
- 长时间无 `generated/action-{slot}.mp4`
- review issues 含「底片不可见/纯黑」但 `completionMode=hf_native`（agent 误写 base-video overlay）

### 检查项

- `acp-author/{slot}/task.json` → `baseVideoDiagnostics`、`inSessionReviewEnabled`
- `VIDEOMAKER_MATERIAL_REVIEW_ACP_IN_SESSION_REVISE`（scoped 默认 false）
- `VM_ACP_IN_SESSION_REVIEW` 注入 MCP

### 修复（2026-06-29 计划落地）

- Worker `base_video_normalize`（仅 `source_then_polish`）
- scoped regen 默认 post-session review
- per-prompt timeout + lint-passed partial harvest
- hf_native lint 禁止 external base MP4

---

*记录日期：2026-07-01（§10 增补 2026-06-29）*
