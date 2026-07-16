# slot-5 门内改片降耗 E2E — 2026-07-06

**状态：** 已执行（用例 A/B 均跑完；B 因 payload 路由问题未真正测到 `IN_SESSION_REVISE=false`）

## 测试上下文

| 项 | 值 |
|----|-----|
| projectId | `7bed327a-f272-4887-a294-938d30b98723` |
| generationId | `edcae35e-1184-47d4-8b4e-735c79851580` (high_conversion) |
| taskId | `9c707b68-4233-4bb6-9589-3ac55d32c7f5` |
| 对照基线 | trace `5b2c2e658455`（硬化 E2E，wall ~13.2 min） |

**NL 改片指令：** `当前该分镜缺乏核心文字，请加入金句「价值对等才是长久往来的根本」并优化动效，禁止 skeleton 占位`

---

## 用例 A — `VIDEOMAKER_MATERIAL_REVIEW_ACP_IN_SESSION_REVISE=true`（默认）

| 字段 | 结果 |
|------|------|
| traceId | `856afbd419ea`（同轮前序失败 `e71ae807c572`） |
| taskId | `9c707b68-4233-4bb6-9589-3ac55d32c7f5` |
| wall time | **~4.1 min**（08:35:48 → 08:39:53 UTC） |
| producing_media 次数 | **0** ✓ |
| resumed fast path | **有** `(resumed) generation plan ready` ✓ |
| ACP 作者 | **失败** `agentExitCode=1`，`outcome.valid=false`，无 `tool_calls.jsonl` |
| worker 降级 | **有** — `槽位 slot-5: ACP 作者失败，已降级为占位素材` |
| lint_draft 次数 | **N/A**（会话未产出 MCP lint） |
| review_material_preview 次数 | **0** — `review_bypass:no_in_session_marker` |
| repair + preview 一致性 | **未验证**（`preview.mp4` mtime 仍为 14:54） |
| 金句 / specHash | **未达成**（占位收片 `specHash=0825f9d0…`） |
| `_invoke_mcp*.py` | **无** ✓ |
| 结论 | **降耗路径通过，功能未通过** — Fast path 与 wall ≤8 min 达标；Cursor ACP 连续 Internal error，需排查后复测 |

### 用例 A 关键 events

```text
08:35:48 | awaiting_material_review | Retry requested, resuming from checkpoint
08:35:50 | planning_completion      | (resumed) generation plan ready
08:35:50 | generating_material      | Completing slot slot-5
08:39:52 | rendering_material       | 槽位 slot-5: ACP 作者失败，已降级为占位素材
08:39:53 | awaiting_material_review   | Review slot material previews before final assembly
```

---

## 用例 B — 意图：`VIDEOMAKER_MATERIAL_REVIEW_ACP_IN_SESSION_REVISE=false`

| 字段 | 结果 |
|------|------|
| traceId | `67d139254575` |
| wall time | **~8.6 min**（08:52:34 → 09:01:07 UTC） |
| producing_media 次数 | **0** ✓ |
| resumed fast path | **有** ✓ |
| `inSessionReviewEnabled`（session.json） | **true** ⚠️ — `task.json` 无 `materialGateRevise`，未走 `REVISE` env 分支 |
| ACP 作者 | **成功** `valid=true`，`repairAttempt=1`，`turnCount=2` |
| ACP latency | **~510 s**（`totalLatencyMs=510236`） |
| lint_draft（MCP tool_call） | **3** ✓（≤3） |
| review_material_preview（worker） | **1**（video 审片 → `IN_SESSION_REPAIR`） |
| repair + preview 一致性 | **通过** — `preview.mp4` 17:01:02，`material-review-marker.json` 17:01:03 |
| 金句 / specHash | **通过** — bodyHtml 含金句与「价值对等」「长久往来」；`specHash=968d312c…` |
| 审片结论 | **未过**（与基线类似：黑场、层级、静帧）；`approved=false` |
| in-session preview/vision（Case B 目标 0） | **未测到** — 实际仍为 in-session 开 |
| 结论 | **部分通过** — 功能路径与降耗相对基线有效，但 **非** 计划的 B 模式；需修复 `materialGateRevise` 写入 payload 后重跑 B |

### 用例 B 关键 events

```text
08:52:34 | awaiting_material_review | Retry requested, resuming from checkpoint
08:52:35 | planning_completion      | (resumed) generation plan ready
08:52:35 | generating_material      | Completing slot slot-5
09:01:06 | rendering_material       | HyperFrames material ready for slot slot-5
09:01:07 | awaiting_material_review   | Review slot material previews before final assembly
```

---

## 对比汇总

| 指标 | 基线 `5b2c2e658455` | 用例 A | 用例 B（实际 in-session 开） | 目标 |
|------|---------------------|--------|------------------------------|------|
| 总 wall | ~13.2 min | **~4.1 min** | **~8.6 min** | A≤8 / B≤6 |
| producing_media | ~2.6 min | **0** | **0** | 0 |
| lint_draft（MCP） | 10 | N/A | **3** | ≤3 |
| ACP 收片 | 成功+repair | **失败降级** | **成功+repair** | 成功 |
| 金句上屏 | ✓ | ✗ | ✓ | ✓ |

---

## 发现的问题（后续）

1. **用例 A ACP 不稳定：** 连续 trace `e71ae807c572` / `856afbd419ea` 均 `Internal error` + `agentExitCode=1`；同 slot 用例 B 同环境却成功 → 需查 Cursor ACP 偶发失败与降级策略是否应 fail-fast。
2. **用例 B env 未生效：** `storage/.../acp-author/slot-5/task.json` **无** `materialGateRevise` 字段 → `_acp_in_session_review_enabled()` 未读 `VIDEOMAKER_MATERIAL_REVIEW_ACP_IN_SESSION_REVISE`，session 仍为 `inSessionReviewEnabled: true`。
3. **Agent 仍用 shell 调 MCP（trace 67d139254575）：** 出现 `python -c` 直调 handlers，违反 STOP RULES；收片虽成功，应继续 trace policy 收紧。

---

## 操作步骤（归档）

1. Workbench → 素材预览审核 → slot-5 → NL 改片
2. SSE：**不得**出现 `producing_media`；应有 `(resumed) generation plan ready`
3. 用例 B：设 `VIDEOMAKER_MATERIAL_REVIEW_ACP_IN_SESSION_REVISE=false` 并重启 API → **需先修复 `materialGateRevise` payload**

详细 checklist：`docs/demos/material-review-gate-e2e-checklist.md` § Gate revise 降耗
