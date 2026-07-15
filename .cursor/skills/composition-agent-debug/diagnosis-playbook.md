# Composition Agent — Diagnosis Playbook

Use after locating files via [path-map.md](path-map.md). Match **症状 → 看什么 → 结论**.

## A. Author / ACP

| outcome / 现象 | 含义 | 下一步 |
|----------------|------|--------|
| `valid: false` + `Internal error` + **无** `tool_calls.jsonl` | Agent 首轮崩，MCP 未真正跑 | smoke Cursor ACP；查额度/CLI；session retry |
| `valid: false` + `acp_author_missing_material_spec` | 跑了但没写出 spec | 读 `tool_calls.jsonl` 末尾；看是否只有 Read |
| `valid: false` + `acp_mcp_tools_unavailable` / `acp_mcp_tools_missing:*` | list_mcp_tools 空或缺必备工具 | Cursor MCP 挂载；对照 `McpServerStdio` |
| `valid: true` + 空 benefit-card 在 **generated/** | Author OK 但 render/promote 错层 | 查 B 层，不要重开 ACP |
| `agentDiagnostics.agentStillRunning: true` | 子进程未退出 | 查 zombie / kill；timeout 配置 |
| `valid: true` 但产物无金句 / hash 未变 | harvest 了旧 spec 或 mustChangeSpec 未生效 | 比 `task.json` authorContract、新旧 `material-spec.json` specHash |

### MCP vs 绕道（行为质量）

| tool_calls 特征 | 分类 |
|-----------------|------|
| 有 `composition_lint_draft` / `write_material_spec` / `skill_view`，无 repo Read | **理想 MCP 路径** |
| 有 MCP lint，又有 `python -c` + `composition.mcp` | **混合**（结果可能对、路径违规） |
| 几乎只有 Find/Read/grep/`inspect.getsource`，无 MCP 名 | **无效源码探索**；查 MCP 可见性与 prompt |
| `policy_violation` 累计 ≥2 | Trace policy abort；读 follow-up 文案 |

必备 MCP 工具名（server `videomaker-composition`）：  
`write_material_spec`, `composition_lint_draft`, `read_author_brief`, `composition_validate_draft`, `skill_view`（另有 `registry_list`, `composition_lint_scratch_file`, preview/review tools）。

## B. Render / HF

| 现象 | 含义 |
|------|------|
| `generated/...` skeleton、工作台黑屏 | Author fallback 或 render 用了空 spec |
| scratch spec 好、generated 旧 | promote/copy 未跑或仍指向旧 action |
| lint hang 数分钟 | 历史问题；现以 MCP lint + cache 为主；查是否 shell `lint-spec` |

## C. Material review

| report / state | 含义 |
|----------------|------|
| `reviewInputs.mode: video` / `frames` | 正常视觉审片 |
| `reviewInputs.mode: text_only` | 无 vision / gateway 未注入；查 `VM_DATABASE_PATH`、provider |
| `reviewUnavailable: true` + 429 / timeout | 基础设施豁免；不是创意否决 |
| `reviewBypass: no_in_session_marker` | 关了 in-session 且无 marker；看 `GATE_LLM` 是否应在 finalize 补审 |
| `reviewPhase: gate_finalize` | Gate 级 LLM 审片已跑 |
| `approved: false` + `agent_failed` | 创意未过（cap=1 后常交人工门） |
| UI「Agent 审阅不可用」 | 对一下是 bypass / unavailable / text_only，勿一律当失败 |

`model-calls`：该 slot 的 `video_understanding` 次数应 ≤ `MATERIAL_REVIEW_MAX_ROUNDS`（默认 1）；repair follow-up **不应**再产生第二轮 billed vision（`review_cap_no_re_review`）。

## D. Gate revise 路由

| 检查 | 期望 |
|------|------|
| Fast path：SSE 无长时间 `producing_media` | 应有 `(resumed) generation plan ready` |
| `IN_SESSION_REVISE=false` | `session.json.inSessionReviewEnabled === false` |
| `task.json` / `revise-context.json` 含 `materialGateRevise` | 否则可能误走 first-gen 的 `IN_SESSION` env |
| Fast path 过早 `clear_material_gate_revise_context` | payload 丢字段 → env 分支错乱 |

## Latency buckets（门内改片）

粗分 wall，便于对比基线：

| 段 | 证据 |
|----|------|
| ACP session | `outcome.totalLatencyMs` |
| Worker vision | `model-calls` latency sum (`video_understanding`) |
| HF preview/render | tool-runs / 文件 mtime：`preview.mp4` |
| 无效探索 | Read/grep/shell 次数 × 墙钟空隙 |
| producing_media | SSE events（应在 fast path 为 0） |

对照复盘基线时引用：`docs/retrospectives/2026-07-06-gate-revise-latency-e2e.md`。

## Minimal command cookbook

优先用汇总脚本（仓库根目录）：

```powershell
python .cursor/skills/composition-agent-debug/scripts/summarize_acp_trace.py `
  --project-id <projectId> --generation-id <generationId> --slot slot-5
```

手工补充：

```powershell
$project = "<projectId>"
$gen = "<generationId>"
$slot = "slot-5"
$root = "D:\VideoMaker\services\api\storage\projects\$project"

# Scratch + review
Get-ChildItem "$root\generations\$gen\acp-author\$slot"
Get-Content "$root\generations\$gen\material-reviews\$slot\report.json" -Raw | ConvertFrom-Json | Select-Object approved, reviewPhase, reviewBypass, @{n='mode';e={$_.reviewInputs.mode}}

# Latest ACP outcomes for this generation
Get-ChildItem "$root\logs\composition-author\acp" -Directory | ForEach-Object {
  $j = Get-Content (Join-Path $_.FullName "outcome.json") -Raw | ConvertFrom-Json
  if ($j.generationId -eq $gen) { [PSCustomObject]@{ id=$_.Name; valid=$j.valid; ms=$j.totalLatencyMs; at=$j.recordedAt } }
} | Sort-Object at -Descending
```

```powershell
# Count ACP tool patterns for one runId
$tc = "D:\VideoMaker\services\api\storage\projects\$project\logs\composition-author\acp\<runId>\tool_calls.jsonl"
Select-String -Path $tc -Pattern "composition_lint_draft|write_material_spec|skill_view|python -c|policy_violation|handlers\.py" | Group-Object Pattern | Sort-Object Count -Descending
```
