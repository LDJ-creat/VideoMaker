# Generation Script Review E2E Checklist

Prerequisites: API + worker + web running; ModelGateway text provider configured; optional video provider for short-form path.

## Duration target

- [ ] Open project workbench → **录入** panel shows **目标时长**
- [ ] Recommendation matches analyzed sample `metadata.durationSec`
- [ ] Set target ≤60s → hint shows short-form strategy
- [ ] Set target >60s → hint shows long-form composed strategy
- [ ] Start generation → brief persists `durationTarget`

## Master review (per variant)

- [ ] Dual-variant run pauses both tasks at `awaiting_master_review`
- [ ] Progress panel shows amber **前往脚本审核** (not failed)
- [ ] **脚本审核** tab shows independent variant tabs
- [ ] Edit master text → **保存草稿** → reload preserves edits
- [ ] **批准总脚本并生成分镜** resumes task → stage `drafting_storyboard`

## Storyboard review

- [ ] Task pauses at `awaiting_storyboard_review`
- [ ] Inline edit scene visual/script → save works
- [ ] **批准分镜并开始生成视频** resumes → material/render stages

## Strategy branch

- [ ] ≤60s: `generation-plan.json` includes `generationStrategy: short_form_direct`
- [ ] >60s: `generationStrategy: long_form_composed` and per-slot material path runs

## Resume / retry semantics

- [ ] Approve routes call `POST /api/tasks/{taskId}/retry` with same task id
- [ ] Failed generation still uses retry from checkpoint (not confused with review pause)

## CI mode

- [ ] `VIDEOMAKER_HUMAN_REVIEW_MODE=false` completes generation without script-review pause
