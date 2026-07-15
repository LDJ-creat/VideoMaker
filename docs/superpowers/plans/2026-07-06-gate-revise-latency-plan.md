# 门内改片降耗实施计划

**Status:** implemented (2026-07-06)  
**Baseline E2E:** `docs/retrospectives/2026-07-06-slot5-acp-hardening-e2e.md` (trace `5b2c2e658455`, wall ~13.2 min)  
**E2E checklist:** `docs/demos/material-review-gate-e2e-checklist.md` § Gate revise 降耗

## 目标

在保留 `VIDEOMAKER_MATERIAL_REVIEW_ACP_IN_SESSION_REVISE`（门内改片可关 in-session 审片）前提下，将 gate NL 改片 wall time 从 ~13 min 压到 ~7–8 min（in-session 开）或 ~5–6 min（in-session 关）。

## 实现摘要

| Phase | 内容 | 关键文件 |
|-------|------|----------|
| 1 | Gate revise retry 跳过 `producing_media`，直进 `generating_material` | `material_slot_revise.py`, `videomaker_pipeline.py` |
| 2 | MCP lint 缓存 + 短 prompt + scratch 摘要收敛 | `acp_prompt.py`, `mcp/handlers.py`, `gate_revise_prompt.py`, `scratch_bootstrap.py` |
| 3 | `VIDEOMAKER_MATERIAL_PREVIEW_PROFILE`；repair 后 re-render preview + marker specHash 同步；stale marker → force render | `material_review.py`, `author.py`, `material_gate_promote.py` |
| 4 | 文档 + E2E checklist | 本目录、AGENTS.md、`.env.example` |

## 环境变量

| Env | Default | 说明 |
|-----|---------|------|
| `VIDEOMAKER_MATERIAL_REVIEW_ACP_IN_SESSION_REVISE` | `true` | 门内 NL 改片是否跑 ACP in-session preview+vision（`false` 仅 lint+人工 gate） |
| `VIDEOMAKER_MATERIAL_PREVIEW_PROFILE` | `full` | in-session preview 渲染：`full` \| `fast`（`fast` 使用 HF `--quality draft --fps 24`） |

Gate revise fast path **无需**额外 env；检测到 `material-slot-revise-queue.json` pending 或 resume 时 `revise-context.materialGateRevise` 即触发。

## 验收

- pytest: `tests/test_gate_revise_fast_path.py`, `test_material_slot_revise.py`, `test_gate_revise_prompt.py`, `test_material_gate_promote.py`
- 手工 E2E：见 checklist § Gate revise 降耗；服务已启动时改代码后直接复测 slot-5
