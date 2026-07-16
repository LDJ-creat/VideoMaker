# ACP 分镜 Agent 硬化与审片 1 次

**Status:** implemented (2026-07-06)  
**Retrospective:** `docs/retrospectives/2026-07-06-gate-revise-display-copy-acp-harvest-session.md`  
**E2E:** `docs/demos/material-review-gate-e2e-checklist.md` § ACP 硬化；`docs/demos/composition-acp-author-e2e-checklist.md` § B1

## 目标

按「硬约束 > 工具 UX > 提示词」分层：

1. 默认 **`VIDEOMAKER_MATERIAL_REVIEW_MAX_ROUNDS=1`**：最多 1 次 billed vision 审片；创意未过仍允许 1 轮 repair follow-up，repair 后不再二审（`review_cap_no_re_review`）。
2. 禁止 scratch 辅助脚本（`_invoke_mcp*.py` 等）与 repo 源文件 Read；trace policy 二次违规 abort。
3. MCP 工具补齐 + scratch bootstrap（`AUTHOR_BRIEF.md`、`SKILLS_SUMMARY.md`）。
4. Terminal 不再放行 `python -m composition.cli lint-spec`；默认 spawn cwd=scratch。

## 环境变量

| Env | Default | 说明 |
|-----|---------|------|
| `VIDEOMAKER_MATERIAL_REVIEW_MAX_ROUNDS` | `1` | Vision 审片上限 |
| `VIDEOMAKER_MATERIAL_REVIEW_REPAIR_FOLLOWUP_MAX` | `1` | 创意未过时的 repair follow-up 次数 |
| `VIDEOMAKER_ACP_SPAWN_CWD` | `scratch` | ACP agent spawn 工作目录 |
| `VIDEOMAKER_ACP_TRACE_POLICY_ENABLED` | `true` | 检测 trace 中 repo Read，第 2 次 abort |
| `VIDEOMAKER_ACP_HELPER_SCRIPT_BLOCK` | `true` | acceptance 拒收 forbidden helper scripts |

## 实现文件

| 模块 | 文件 |
|------|------|
| 审片 cap + repair | `services/worker/app/composition/acp/author.py`, `services/worker/app/pipelines/material_review.py`, `services/composition/composition/author/tools.py` |
| 禁止辅助脚本 | `services/worker/app/pipelines/material_slot_revise.py`, `services/worker/app/composition/acp/acceptance.py` |
| MCP 工具 | `services/composition/composition/mcp/handlers.py`, `server.py` |
| Bootstrap | `services/worker/app/composition/acp/scratch_bootstrap.py` |
| Trace policy | `services/worker/app/composition/acp/trace_policy.py`, `headless_client.py` |
| Terminal | `services/worker/app/composition/acp/terminal_bridge.py` |
| 提示词 | `services/composition/composition/skills/acp_prompt.py` |

## 审片语义（cap=1）

1. 第 1 次 post-turn review 正常执行。
2. 创意未过（非 infra waive、非 hardGate）→ 发 `_build_review_followup`，`review_repair_followups_sent++`。
3. Agent repair + lint 通过 → **跳过** `_review_spec_after_turn`，保留首轮 marker，`skipped_reason=review_cap_no_re_review`。
4. **Hard gate**（预览时长漂移等）始终发 follow-up，不受 cap 阻断。
5. Infra 失败（429 等）维持现有 waive。

## 自动化测试

```powershell
cd services/worker
python -m pytest tests/test_acp_author.py tests/test_acp_acceptance.py tests/test_material_slot_revise.py tests/test_material_review_infrastructure.py tests/test_trace_policy.py tests/test_terminal_bridge.py -q

cd services/composition
python -m pytest tests/test_mcp_server.py tests/test_react_material_review_tools.py -q
```

## 手工 E2E（slot-5 门内改片）

见 `docs/retrospectives/2026-07-06-slot5-acp-hardening-e2e.md`。

## 回滚

- `VIDEOMAKER_MATERIAL_REVIEW_MAX_ROUNDS=2`
- `VIDEOMAKER_ACP_TRACE_POLICY_ENABLED=false`
- `VIDEOMAKER_ACP_HELPER_SCRIPT_BLOCK=false`
