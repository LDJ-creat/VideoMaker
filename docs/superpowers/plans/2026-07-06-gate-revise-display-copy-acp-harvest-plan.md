# Gate Revise Display Copy + ACP Harvest + Prompt

**Status:** implemented (2026-07-06)

## Summary

Fixes three failure chains observed in slot-5 material gate NL revise:

1. **Display copy policy** — gate revise derives `allowedDisplayCopy` from storyboard script, quoted authorPrompt phrases, and packaging overlay; writes `authorContract` + `renderPolicy` into revise-context, plan finishBrief, and ACP `task.json`.
2. **Anti-regression** — clears ACP scratch artifacts on regen; `_harvest_material_spec` rejects stale primary spec; `accept_acp_author_result` blocks unchanged specHash, stale harvest, abnormal exit, and gate revise partial harvest.
3. **ACP hardening** — slim L0 system prompt; fixture lint only under `VIDEOMAKER_FIXTURE_MODE` or pytest; MCP lint timeout 90s; structured follow-ups with `hintCode` / `forbiddenAction: read_repo_source`.

## Key modules

| Module | Role |
|--------|------|
| `services/worker/app/pipelines/display_copy_policy.py` | derive allowlist, infer full regen, build authorContract |
| `services/worker/app/pipelines/material_slot_revise.py` | prepare regen + scratch clear + plan patch |
| `services/worker/app/composition/acp/acceptance.py` | post-session acceptance gate |
| `services/composition/composition/skills/acp_prompt.py` | slim ACP system prompt |
| `services/composition/composition/author/lint_errors.py` | `forbidden_copy_empty_allowlist` hint |

## Verification

```powershell
cd services/worker
python -m pytest tests/test_display_copy_policy.py tests/test_material_slot_revise.py tests/test_acp_author.py tests/test_acp_acceptance.py tests/test_material_review_author_payload.py -q

cd services/composition
python -m pytest tests/test_forbidden_copy_guard.py tests/test_acp_prompt.py tests/test_mcp_server.py -q
```

Manual E2E: material-review gate NL revise with「请加核心文字重新生成」→ verify `authorContract.allowedDisplayCopy`, new specHash, fresh material review (not cached text_only marker).

## Env notes

- `VM_ACP_FIXTURE_LINT` is **not** passed to ACP MCP child processes; use `VIDEOMAKER_FIXTURE_MODE=true` for CI/smoke only.
- Gate revise blocks silent ACP partial harvest when `mustChangeSpec=true`.
