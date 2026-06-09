# Generation Script Review E2E Checklist

Prerequisites: API + worker + web running; ModelGateway text provider configured.

## Duration target

- [ ] Open project workbench → **录入** panel shows **目标时长**
- [ ] Recommendation matches analyzed sample `metadata.durationSec`
- [ ] Duration hint shows unified composed strategy (not short/long split)
- [ ] User selects **成片画幅** explicitly in Brief (not auto-switched by duration)
- [ ] Start generation → brief persists `durationTarget` and `aspectRatio`

## Master review (per variant)

- [ ] Dual-variant run pauses both tasks at `awaiting_master_review`
- [ ] Progress panel shows amber **前往脚本审核** (not failed)
- [ ] **脚本审核** tab shows independent variant tabs
- [ ] Edit master text → **保存草稿** → reload preserves edits
- [ ] **自然语言改脚本** (master): enter instruction → **应用修改** → master textarea updates; optional summary line shown
- [ ] Multi-round NL (no chat history): second instruction applies to current draft text only (prior instruction text not sent to LLM)
- [ ] **批准总脚本并生成分镜** resumes task → stage `drafting_storyboard`

## Storyboard review

- [ ] Task pauses at `awaiting_storyboard_review`
- [ ] Inline edit scene visual/script → save works
- [ ] **自然语言改脚本** (storyboard): instruction revises scenes; master text unchanged (already approved)
- [ ] **批准分镜并开始生成视频** resumes → material/render stages

## NL revise debug artifacts

- [ ] After NL revise: `generations/{generationId}/script-nl-revisions/{revisionId}/` contains `meta.json`, `inputs.json`, `raw-output.json`, `normalized.json`
- [ ] `generations/{generationId}/script-nl-revisions/index.jsonl` appends one line per revise
- [ ] `GET /api/generations/{generationId}/agent-runs` lists `storyboard_writer` run with matching `generationId`
- [ ] Task remains `awaiting_review` after NL revise (no retry until approve)

## Generation strategy

- [ ] Any target duration: `generation-plan.json` includes `generationStrategy: long_form_composed`
- [ ] Per-slot material completion runs for weak/missing visual slots
- [ ] Legacy artifacts with `short_form_direct` still resume after normalize

## Resume / retry semantics

- [ ] Approve routes call `POST /api/tasks/{taskId}/retry` with same task id
- [ ] Failed generation still uses retry from checkpoint (not confused with review pause)

## CI mode

- [ ] `VIDEOMAKER_HUMAN_REVIEW_MODE=false` completes generation without script-review pause
