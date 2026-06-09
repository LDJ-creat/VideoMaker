# Script Draft NL Revise Plan

**Date:** 2026-06-09  
**Status:** Implemented

## Summary

Adds natural-language script revision during human review gates (`awaiting_master_review`, `awaiting_storyboard_review`). Each request is stateless: LLM receives current `script-draft.json` + new instruction only (no multi-turn chat history).

## User flow

1. Generation pauses at master or storyboard review (existing behavior).
2. User opens **脚本审核** → **自然语言改脚本** bar.
3. User enters instruction → **应用修改** (syncs UI draft, then calls API).
4. Worker runs `storyboard_writer` with `phase=revise_master|revise_storyboard` via `AgentRunner`.
5. Updated draft shown in editor; user may NL-revise again, manually edit, or approve.

## API

```http
POST /api/generations/{generation_id}/script-draft/nl-revise
{ "scope": "master" | "storyboard", "instruction": "..." }
→ { "draft", "revisionId", "summary?" }
```

Gate validation in `script_draft_service.validate_nl_revise_gate`.

## Worker

- `app/pipelines/script_draft_revise.py` — orchestration + revision debug artifacts
- `run_p0_task.py` mode `revise_script_draft`
- `storyboard_writer` phases: `revise_master`, `revise_storyboard`

## Debug artifacts

```text
generations/{generationId}/script-nl-revisions/{revisionId}/
  meta.json, inputs.json, raw-output.json, normalized.json, error.json (on failure)
generations/{generationId}/script-nl-revisions/index.jsonl
```

Standard `AgentRunLog` under `projects/{projectId}/logs/agent-runs/`.

## Web

- `ScriptNlReviseBar` in `ScriptReviewPanel` (master + storyboard sections)
- `apiClient.nlReviseScriptDraft`

## Verification

- `services/worker/tests/test_script_draft_revise.py`
- `services/api/tests/test_script_draft_nl_revise_routes.py`
- `apps/web/tests/script-review-panel.test.tsx`
- E2E: `docs/demos/generation-script-review-e2e-checklist.md` § NL revise

## Out of scope (v1)

- Multi-turn LLM conversation / `revisionHistory` in prompts
- NL revise after approve or outside review gates
- Reuse of `POST /revise` / `EditIntent` pipeline
