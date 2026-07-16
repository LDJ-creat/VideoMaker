# slot-5 ACP 硬化 E2E — 2026-07-06

**状态：** 已执行（2026-07-06 14:46–14:59 本地）

## 测试上下文

| 项 | 值 |
|----|-----|
| projectId | `7bed327a-f272-4887-a294-938d30b98723` |
| generationId | `edcae35e-1184-47d4-8b4e-735c79851580` (high_conversion) |
| taskId | `9c707b68-4233-4bb6-9589-3ac55d32c7f5` |
| traceId | `5b2c2e658455` |
| 对照 trace（上次） | `931b45225e9e` |

**NL 改片指令：** 当前该分镜缺乏核心文字，请加入金句「价值对等才是长久往来的根本」并优化动效，禁止 skeleton 占位

**Env：** `AUTHOR_BACKEND=acp`, `ACP_AGENT=cursor`, `reviewMaxRounds=1`（session.json 确认）

---

## 评估摘要

| 维度 | 结论 |
|------|------|
| A. 硬约束 | **通过** |
| B. MCP 规范 | **部分通过**（Read 次数仍偏高） |
| C. 审片 1 次 + repair | **通过** |
| D. 耗时 | **通过** |
| E. 产物质量 | **部分通过**（金句已上屏，审片创意未过 → 待人工） |
| **总评** | **部分通过** |

---

## 详细指标

- **traceId:** `5b2c2e658455`
- **taskId:** `9c707b68-4233-4bb6-9589-3ac55d32c7f5`
- **wall time:** **13.2 min**（14:46:41 提交 → 14:59:50 回到 `awaiting_material_review`）
- **ACP session latency:** **9.8 min**（`outcome.json` `totalLatencyMs=589835`）
- **Read/grep 次数:** **13**（`tool_calls.jsonl` 中含 Read/grep 的 session_update）/ **forbidden paths: 无**
- **_invoke_mcp.py:** **无**
- **review_material_preview 次数:** **1**（model-call `10a5032b-6e96-4ccf-8fbe-5be55016735d`，video 模式，~138s）
- **repair follow-up:** **有**（`turnCount=2`，`IN_SESSION_REPAIR` ×1，`hintCode=material_review`）
- **skipped_reason=review_cap_no_re_review:** **有**（`acp-5b2c2e658455-turn_review_gate-60.json`）
- **specHash 变化:** **是**（`e12c7fda…` → `eb148275…`）
- **结论:** **部分通过**（硬化机制生效；Read 探索仍偏多；创意审片 1 轮否 → repair 后收片进人工门符合设计）

---

## A. 硬约束

| 检查项 | 结果 |
|--------|------|
| scratch 无 `_invoke_mcp.py` / `_mcp_call*.py` | ✅ 仅 lint/preview/spec/bootstrap 文件 |
| 收片未拒收 | ✅ task 终态 `awaiting_review` / `awaiting_material_review` |
| specHash 变化 | ✅ |

---

## B. MCP 规范

| 检查项 | 结果 |
|--------|------|
| MCP lint ≥ 1 | ✅ `composition_validate_draft`×5, `composition_lint_draft`×10, `composition_lint_scratch_file`×1 |
| `read_author_brief` / bootstrap | ✅ `read_author_brief`×2；scratch 含 `AUTHOR_BRIEF.md` + `SKILLS_SUMMARY.md` |
| 无 `VM_ACP_FIXTURE_LINT` | ✅ |
| Read ≤ 5 且无 repo 路径 | ⚠️ Read 类 update **13 次**（较上次 16 次下降），**无** `services/`/`tests/` 路径 |
| 无 shell `_invoke_mcp` | ✅ |
| trace policy 违规 | ✅ 0 次 `policy_violation` |

---

## C. 审片 1 次 + repair 语义

| 检查项 | 结果 |
|--------|------|
| vision 调用 = 1 | ✅ turn1 `reviewRoundsUsed=1`，latency ~157s |
| repair 对话 | ✅ turn2 lint 通过后 `turn_followup` + 审片意见驱动 repair |
| repair 后无第二轮审片 | ✅ turn2 `skippedReason=review_cap_no_re_review` |
| 审片模式 | ✅ **video**（非上次 text_only/429） |
| 工作台状态 | ✅ `agent_failed`（创意未过，符合 cap=1 人工兜底） |

---

## D. 耗时对比

| 指标 | 上次 (931b45225e9e) | 本次 | 目标 |
|------|---------------------|------|------|
| 总 wall | ~982s (~16.4 min) | **~789s (~13.2 min)** | ≤ 12–15 min |
| lint hang | ~4–6 min | **0**（无卡死段） | 0 |
| ACP 会话 | ~982s | **~590s** | — |
| Worker 审片 | ~2 轮 | **1 轮** (~157s) | ~2.5–4 min |

---

## 降耗优化（2026-07-06 E2E 已跑）

见 `docs/retrospectives/2026-07-06-gate-revise-latency-e2e.md` 与 plan `docs/superpowers/plans/2026-07-06-gate-revise-latency-plan.md`。

| 指标 | 基线 (5b2c2e658455) | 降耗 A (856afbd419ea) | 降耗 B (67d139254575) | 目标 |
|------|---------------------|------------------------|------------------------|------|
| 总 wall | ~13.2 min | **~4.1 min**（ACP 失败降级） | **~8.6 min**（成功+repair） | A≤8 / B≤6 |
| producing_media | ~2.6 min | **0** | **0** | 0 |
| lint_draft (MCP) | 10 | N/A | **3** | ≤3 |
| Fast path | 无 | **有** | **有** | 有 |

---

## E. 产物质量

- **spec 含金句：** ✅ `material-spec.json` bodyHtml 含「价值对等才是长久往来的根本」及关键词「价值对等」「长久往来」
- **非 skeleton：** ✅ composition 模板 + GSAP timeline
- **allowedDisplayCopy：** ✅ `AUTHOR_BRIEF.md` / `task.json` 契约完整
- **审片意见（首轮 video）：** 前半句与全句重叠、beat2 层级乱、~1.1s 静帧 → repair 后未再审，**人工门待处理**（预期行为）

---

## 观察与后续

1. **硬化收益明确：** 无辅助脚本、无 lint hang、审片 1+repair 语义正确、总时长降 ~3 min。
2. **Read 仍偏多（13）：** 虽无 repo 越狱，但未达 plan 目标 ≤5；可继续收紧 bootstrap 摘要长度或 trace policy 对 scratch 外 Read 更敏感。
3. **cap=1 质量权衡：** 首轮 video 审片已识别动效/层级问题，repair 轮无法二次 video 验证 → `agent_failed` 交给人工 gate，与产品设计一致。
