# Material Review Gate E2E Checklist

**Plan:** `docs/superpowers/plans/2026-06-29-material-review-gate-plan.md`

## Prerequisites

- Model gateway: vision and/or video understanding configured for agent review
- `VIDEOMAKER_HUMAN_REVIEW_MODE=true` (default)
- `VIDEOMAKER_MATERIAL_REVIEW_ENABLED=true` (default)
- HyperFrames CLI available at repo root

## Flow

1. Complete master + storyboard script review (existing flow).
2. Observe `generating_material` runs **visual slots only** (no global TTS yet).
3. HF terminal slots: author session uses `render_material_preview` → `review_material_preview` before submit.
4. Task pauses at `awaiting_material_review` with `status=awaiting_review`.
5. Workbench **素材预览审核** panel lists slots + review reports.
6. Optional: NL revise one slot → preview updates, still same `generationId`.
7. **批准素材并继续成片** → `assembling_final` → global TTS → timeline → MP4.

## Verification

- [ ] Pure stock/reuse slots: report `reviewInputs.mode=skipped`, no gateway reviewer call
- [ ] HF / `-finish` slots: agent review with video or vision route
- [ ] ReAct/ACP auto-repair stays in single session (no new ACP session for repair)
- [ ] Gate NL revise uses new author session + `existingMaterialSpec`
- [ ] Gate NL「加核心文字/重新生成」：`revise-context.json` / ACP `task.json` 含非空 `authorContract.allowedDisplayCopy`
- [ ] Gate regen 后 `specHash` 必须变化；未变化时 task 失败且 hint 含 `regression_unchanged_spec`
- [ ] Gate regen 清 ACP scratch（`material-spec.json`、`material-review-marker.json`）；vision review 重跑，非旧 `text_only` 缓存
- [ ] `approve-material` produces `master.wav` and final MP4
- [ ] `VIDEOMAKER_HUMAN_REVIEW_MODE=false` skips material gate
- [ ] Dual-variant: each generation pauses/resumes independently

## ACP 硬化（2026-07-06）

**Plan:** `docs/superpowers/plans/2026-07-06-acp-agent-hardening-plan.md`

Gate 内 slot NL 改片 + ACP author 时：

- [ ] `VIDEOMAKER_MATERIAL_REVIEW_MAX_ROUNDS=1`（默认）：`review_material_preview` **成功 billed 调用 = 1**
- [ ] 创意未过：存在 **1 条** `IN_SESSION_REPAIR` + `hintCode=material_review`；repair 后 **无** 第二次 vision 审片
- [ ] observability：`skipped_reason=review_cap_no_re_review`（repair 后跳过再审）
- [ ] scratch **无** `_invoke_mcp.py` / `_mcp_call*.py`；收片非 `forbidden_helper_script`
- [ ] `tool_calls.jsonl`：MCP lint ≥ 1（`composition_lint_draft` / `composition_validate_draft` / `composition_lint_scratch_file`）
- [ ] bootstrap：`AUTHOR_BRIEF.md` + `SKILLS_SUMMARY.md` 在 scratch；优先 `read_author_brief` MCP
- [ ] trace：Read/grep **无** `services/`、`tests/` 路径；第 2 次 repo Read → `acp_policy_violation:read_repo_source`
- [ ] Terminal：**拒绝** `python -m composition.cli lint-spec`（须用 MCP lint）

## Gate revise 降耗（2026-07-06）

**Plan:** `docs/superpowers/plans/2026-07-06-gate-revise-latency-plan.md`  
**前置：** API + Web 已启动；generation 处于 `awaiting_material_review`；ACP + video understanding 已配置（in-session 开模式）。

### Fast path（Phase 1）

- [ ] 门内 NL 改片 retry 后 task events **无** `producing_media`
- [ ] **有** `generating_material`；`(resumed) generation plan ready` 出现

### Lint 收敛（Phase 2）

- [ ] `tool_calls.jsonl`：`composition_lint_draft` + `composition_lint_scratch_file` **合计 ≤ 3**
- [ ] 无 `_invoke_mcp*.py`；MCP lint 缓存同 specHash 返回 `cached: true`

### In-session 开关（Phase 3）

**用例 A — `VIDEOMAKER_MATERIAL_REVIEW_ACP_IN_SESSION_REVISE=true`（默认）**

- [ ] `review_material_preview` billed = **1**；repair 后有 `review_cap_no_re_review`
- [ ] repair 后 `preview.mp4` mtime **晚于** repair turn；`should_materialize_final` 非 stale copy

**用例 B — `VIDEOMAKER_MATERIAL_REVIEW_ACP_IN_SESSION_REVISE=false`**

- [ ] trace **无** in-session preview/vision
- [ ] 仍回到 `awaiting_material_review`

### 耗时目标（对比 trace `5b2c2e658455`）

| 指标 | 基线 | 目标 |
|------|------|------|
| 总 wall | ~13.2 min | A: ≤8 min；B: ≤6 min |
| producing_media | ~2.6 min | 0 |
| lint_draft 次数 | 10 | ≤3 |

## Observability

After HF slot review (live gateway, not skipped):

- [ ] `storage/projects/{projectId}/logs/model-calls/*.json` contains `agentName=material_reviewer` and `slotId`
- [ ] `storage/projects/{projectId}/logs/agent-runs/*.json` contains `agentName=material_reviewer` (video/vision routes)
- [ ] `storage/projects/{projectId}/logs/tool-runs/review_material_preview-*.json` exists for **author-session** review (ReAct/ACP `review_material_preview` tool; gate finalize path does not emit tool-runs)
- [ ] `generations/{generationId}/material-reviews/{slotId}/report.json` includes `trace.reviewRoute` and, when LLM ran, `trace.modelCallId` / `trace.agentRunId`
- [ ] ACP path: MCP child review tool-run `metadata.parentObservabilityRunId` matches parent ACP session run id
- [ ] `GET /api/generations/{id}/model-calls` and `GET /api/generations/{id}/agent-runs` list material_reviewer entries for the generation

Respects `VIDEOMAKER_OBSERVABILITY_CAPTURE` (`full` | `summary` | `off`).

## API

```http
GET /api/generations/{id}/material-review
POST /api/generations/{id}/material-slots/{slotId}/revise
POST /api/generations/{id}/approve-material
```

## Revise fork (全片拆解 · material_regen)

**Plan:** `docs/superpowers/plans/2026-06-30-revise-material-review-gate-plan.md`

### Prerequisites

- Completed generation with MP4 on result/narration panel
- `VIDEOMAKER_MATERIAL_REVIEW_ENABLED=true` (default)
- `VIDEOMAKER_MATERIAL_REVIEW_ON_REVISE=true` (default)

### Flow

1. Open **全片拆解**, pick a scene → **完全重生成** or **微调修改**, submit NL instruction.
2. Confirm **改片方案** (RevisePlanCard shows “执行后将暂停于素材预览审核…”).
3. Execute fork → progress pauses at `awaiting_material_review` on **new generationId**.
4. **素材预览审核** panel shows `改片 fork` banner; affected slots marked **改片**, others **继承**.
5. HF affected slots: LLM `material_reviewer` report visible after regen.
6. Optional: gate内 `POST .../material-slots/{slotId}/revise` → same generationId, preview updates.
7. **批准素材并继续成片** → timeline + final MP4 on fork generation.

### Verification

- [ ] Fork regen stops at material gate (not direct render)
- [ ] Unaffected slots keep `agent_passed` and do not block approve
- [ ] `GET material-review` returns `reviseContext.affectedSlotIds`
- [ ] Gate内 slot revise does not fork again
- [ ] `VIDEOMAKER_MATERIAL_REVIEW_ON_REVISE=false` restores legacy direct-render revise fork
- [ ] Master/storyboard review **not** re-opened on revise fork
