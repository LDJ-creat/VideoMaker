# Composition ACP Author Plan

**Status:** in progress  
**Branch:** `feature/composition-acp-author`  
**Worktree:** `D:\VideoMaker\.worktrees\composition-acp-author`  
**E2E checklist:** `docs/demos/composition-acp-author-e2e-checklist.md`

## Goal

Optional HyperFrames material author backend via ACP external agents (Claude Code, Codex, Cursor). Python MCP exposes composition tools; worker acts as headless ACP Client; render/artifact paths unchanged.

## Env

| Env | Default |
|-----|---------|
| `VIDEOMAKER_COMPOSITION_AUTHOR_BACKEND` | `react` |
| `VIDEOMAKER_COMPOSITION_ACP_AGENT` | `claude` |
| `VIDEOMAKER_COMPOSITION_ACP_AGENT_COMMAND` | (empty) |
| `VIDEOMAKER_COMPOSITION_ACP_TIMEOUT_SEC` | `600` |
| `VIDEOMAKER_COMPOSITION_ACP_AUTO_APPROVE` | `true` |
| `VIDEOMAKER_COMPOSITION_ACP_LINT_REPAIR_MAX` | `1` |
| `VIDEOMAKER_COMPOSITION_LINT_CACHE` | `true` |

## Modules

- `services/composition/composition/mcp/` — MCP stdio server
- `services/worker/app/composition/acp/` — headless ACP client + fake agent for tests

## Related plan

- **Lint CLI + session 内迭代 + 加速（不降质量）：** [`2026-06-19-acp-lint-cli-plan.md`](2026-06-19-acp-lint-cli-plan.md)
  - `python -m composition.cli lint-spec`
  - `lint_pipeline` + spec hash 跳过后置 HF lint + render 复用
  - `VIDEOMAKER_COMPOSITION_LINT_CACHE`, `VIDEOMAKER_COMPOSITION_ACP_LINT_REPAIR_MAX`

## Out of scope (v1)

- Workbench UI agent picker
- ACP session resume across slots
- Replacing `storyboard_writer`
