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
- [ ] `approve-material` produces `master.wav` and final MP4
- [ ] `VIDEOMAKER_HUMAN_REVIEW_MODE=false` skips material gate
- [ ] Dual-variant: each generation pauses/resumes independently

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
