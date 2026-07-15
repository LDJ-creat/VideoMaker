---
name: composition-agent-debug
description: >-
  Debug VideoMaker composition material author (internal ReAct or external ACP
  Cursor/Claude/Codex) using on-disk traces, tool-runs, model-calls, scratch
  artifacts, and material-review reports. Use when analyzing slow/failed slot
  authoring, gate NL revise, lint/MCP bypass, in-session review, ACP Internal
  error, or when the user names projectId/generationId/slotId/traceId and asks
  to diagnose agent behavior from logs.
---

# Composition Agent Debug

Analyze **分镜素材作者**（ReAct / ACP）时：**先读落盘产物，再下结论；不要猜环境或重跑全链路。**

## When to use

- 用户给出 `projectId` / `generationId` / `slotId` / `taskId` / ACP `traceId`（runId）
- 问：为何慢、为何降级占位、为何无金句、lint 路径不对、源码探索、审片 bypass、MCP 未用
- 对比两次改片 / 硬化前后行为

## Storage root（本地 dev）

默认（`run-dev.ps1` → API `storage`）：

```text
services/api/storage/projects/{projectId}/
```

少数脚本/测试可能用仓库根 `storage/projects/`。若路径不存在，先 `Glob **/projects/{projectId}/generations/{generationId}` 定位真实 root。

完整路径表见 [path-map.md](path-map.md)。常见失败判据见 [diagnosis-playbook.md](diagnosis-playbook.md)。

## Helper script（优先用）

稳定汇总 ACP run（outcome / session / tool 行为分类 / scratch / material-review）：

```powershell
cd D:\VideoMaker
python .cursor/skills/composition-agent-debug/scripts/summarize_acp_trace.py `
  --project-id <projectId> --list

python .cursor/skills/composition-agent-debug/scripts/summarize_acp_trace.py `
  --project-id <projectId> --generation-id <generationId> --slot slot-5

python .cursor/skills/composition-agent-debug/scripts/summarize_acp_trace.py `
  --project-id <projectId> --run-id <traceId> --json
```

`behaviorClass`：`mcp_clean` | `mcp_mixed_shell` | `shell_bypass` | `exploration_only` | `no_tool_calls`。  
Cursor 原生 MCP 在 jsonl 里常显示为 `title=MCP: tool`（`kind=other`），工具名可能被省略；shell 直调 handlers 会计入 `shellBypass`。

## Quick ID map

| 用户/UI 说的 | 磁盘关键 |
|--------------|----------|
| projectId | `projects/{projectId}/` |
| generationId | `generations/{generationId}/` |
| slotId（如 slot-5） | `acp-author/{slotId}/`、`material-reviews/{slotId}/`；render 多为 `generated/action-{slot}/` 或 completionAction id |
| ACP trace / runId | `logs/composition-author/acp/{runId}/`（12 位 hex） |
| ReAct runId | `logs/composition-author/{runId}/`（**无** `acp/` 段） |
| taskId | filter `agent-runs` / `model-calls` / `tool-runs` JSON 字段；SSE 任务事件在 API SQLite，产物侧以 generation 为准 |

## Workflow（必须按序）

### 0. 锁定坐标

向用户确认或从消息提取：`projectId`、`generationId`、`slotId`（可选 `taskId`、时间窗）。  
列出目录确认 root：

```powershell
$p = "services/api/storage/projects/{projectId}"
Test-Path "$p/generations/{generationId}"
Get-ChildItem "$p/logs/composition-author" -ErrorAction SilentlyContinue
```

### 1. 分清故障层（先判层，再挖 trace）

| 层 | 看什么 | 成功标志 |
|----|--------|----------|
| A. Author（Agent） | ACP `outcome.json` / ReAct `outcome.json` + scratch `material-spec.json` | `valid: true`；scratch 有非 fallback spec |
| B. Render（HF） | `generated/.../material-spec.json`、preview mp4、`.lint-passed*` | 预览可播；非空 benefit-card skeleton |
| C. Review（审片） | `material-reviews/{slot}/report.json`、`material-review-state.json` | `reviewInputs.mode` 为 `video`/`frames`；或明确 `reviewBypass` |
| D. Gate / revise 路由 | `revise-context.json`、`acp-author/.../task.json` 的 `materialGateRevise` | gate revise 时应有 editInstruction / affectedSlotIds |

**空 benefit-card + 空 params** → 几乎总是 Author 失败后的 **legacy fallback**，不是 lint/审片问题。

### 2. 定位本次 Agent run

**ACP**（`VIDEOMAKER_COMPOSITION_AUTHOR_BACKEND=acp`）：

```text
{root}/logs/composition-author/acp/{runId}/
  session.json      # inSessionReviewEnabled, timeouts, scratchDir, agentCommand
  prompt.json       # system + user
  tool_calls.jsonl  # session_update / MCP / Read / Shell / policy_violation
  outcome.json      # valid, totalLatencyMs, validationErrors, agentDiagnostics
```

按 `generationId` / 时间筛选最近 run：

```powershell
$acp = "services/api/storage/projects/$project/logs/composition-author/acp"
Get-ChildItem $acp -Directory | ForEach-Object {
  $o = Join-Path $_.FullName "outcome.json"
  if (Test-Path $o) {
    $j = Get-Content $o -Raw | ConvertFrom-Json
    [PSCustomObject]@{ id=$_.Name; valid=$j.valid; ms=$j.totalLatencyMs; gen=$j.generationId; at=$j.recordedAt; err=($j.validationErrors -join ';') }
  }
} | Sort-Object at -Descending | Select-Object -First 15
```

**ReAct**（backend=`react`）：

```text
{root}/logs/composition-author/{runId}/   # 注意：不是 .../acp/{runId}
  session/turns/outcome（以实际文件名为准）
```

并行观测（按 `generationId` 过滤）：

```text
{root}/logs/agent-runs/*.json
{root}/logs/model-calls/*.json      # vision / video_understanding / text
{root}/logs/tool-runs/*.json        # acp_session_*、review_material_preview、MCP 相关
```

### 3. 对照 scratch 与 gate 产物

```text
generations/{generationId}/
  acp-author/{slotId}/
    task.json                 # author brief / materialGateRevise / authorContract
    material-spec.json        # Agent 交卷规格
    material-review-marker.json  # in-session 审片通过标记（若有）
    AUTHOR_BRIEF.md / SKILLS_SUMMARY.md  # bootstrap（若开启）
  material-reviews/{slotId}/report.json
  material-review-state.json
  revise-context.json         # 门内改片上下文（可能先于/独立于 task.json）
  generated/{actionId}/...    # 渲染侧 spec / composition / preview
  checkpoint.json             # 流水线阶段
```

### 4. 量化行为（从 tool_calls / model-calls）

对 ACP `tool_calls.jsonl` 统计（PowerShell / 短 Python 均可）：

- Read / Grep / Shell(`execute`) 次数
- 是否出现 `policy_violation`
- 是否 `python -c`、`composition.mcp`、`inspect.getsource`、`_invoke_mcp`
- MCP 工具名是否出现：`composition_lint_draft`、`skill_view`、`write_material_spec`、`read_author_brief`
- `sessionUpdateDropped`（若 outcome/diagnostics 有）

对 `model-calls`：`profile=video_understanding` 次数（对应该 slot 的 billed 审片）。

### 5. 写结论（固定结构）

用中文、简短报告：

1. **故障层**：A/B/C/D 哪一层  
2. **证据**：文件路径 + 关键字段（`valid`、`reviewBypass`、`inSessionReviewEnabled`、specHash、latency）  
3. **Agent 行为**：MCP 正常 / MCP 混合 shell / 纯探索 / 首轮崩溃无 tool_calls  
4. **是否符合设计**：如 `IN_SESSION_REVISE=false` 时期望无 in-session vision、gate LLM 应由 `GATE_LLM` 补审  
5. **下一步**：改 env / prompt / fail-fast / 仅复测该 slot，避免无依据全量重跑

## Anti-patterns

- 未打开 `outcome.json` / `report.json` 就改代码  
- 把 `review_bypass:no_in_session_marker` 当成「Agent 创意失败」  
- 把 HF 渲染失败当成 ACP 失败（或相反）  
- 假设 storage 总在仓库根 `storage/`（本地多为 `services/api/storage/`）  
- 把 ReAct 的 `logs/composition-author/{id}` 与 ACP 的 `.../acp/{id}` 混目录

## Related docs（需要深挖时再读）

- `docs/demos/composition-acp-author-e2e-checklist.md`
- `docs/demos/material-review-gate-e2e-checklist.md`
- `docs/retrospectives/2026-07-01-acp-internal-error-material-review-video-timeout-session.md`
- `docs/retrospectives/2026-07-06-slot5-acp-hardening-e2e.md`
- `docs/retrospectives/2026-07-06-gate-revise-latency-e2e.md`
