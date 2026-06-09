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
