# NL Revise E2E Checklist

## Plan + confirm flow

- [ ] Complete a generation (`succeeded`)
- [ ] Open **结果** → enter NL instruction → **提交改片**
- [ ] **改片方案** card appears (summary, cost tier, steps) — task does **not** start yet
- [ ] **确认执行** starts task; progress panel shows revise stages
- [ ] **取消** dismisses draft plan without task

## In-place patch (low cost)

- [ ] Instruction: `字幕少一点`
- [ ] Plan shows `就地更新` + `subtitle_patch`
- [ ] After execute, same `generationId`; new MP4 when render completes

## Tier 1 — packaging scene patch (in_place)

- [ ] Instruction: `最后一镜标题卡背景改成深色`
- [ ] Plan shows `就地更新` + `packaging_scene_patch` + affected slot/scene ids
- [ ] Same `generationId`; `generated/` unchanged; MP4 re-rendered

## Tier 2 — scoped material regen (medium fork)

- [ ] Instruction: `最后一镜画面背景换成深色合成`
- [ ] Plan shows `Fork 新版本` + `material_regen` + `affectedSlotIds`
- [ ] New `generationId`; only targeted slot material tasks run

## Tier 3 — packaging-only fork (medium-low)

- [ ] Instruction: `全片包装改成 minimal`
- [ ] Plan shows `Fork 新版本` + `packaging_agent`; no full AIGC regen
- [ ] New `generationId`; `packaging_designer` + timeline + render only

## Fork revise (high cost)

- [ ] Instruction: `开头更抓人`
- [ ] Plan shows `Fork 新版本`
- [ ] New `generationId` after execute; source generation unchanged

## Multi-turn session

- [ ] Second instruction in same session (e.g. `再少一点`)
- [ ] **改片对话** panel shows prior turn
- [ ] Planner receives session context (fixture / live)

## Legacy shortcut

- [ ] `POST /revise` still works (plan + execute in one call)
