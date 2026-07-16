# Composition Agent — Path Map

All paths relative to **storage root**:

```text
services/api/storage/   # local run-dev default
# OR
storage/                # alternate / some tooling
```

Below: `{root}` = `…/storage/projects/{projectId}`.

## Generation artifacts

```text
{root}/generations/{generationId}/
  checkpoint.json
  generation-plan.json
  script-draft.json
  revise-context.json              # gate / fork revise snippet
  material-review-state.json     # per-slot status, reviewBypass, report URIs
  acp-author/{slotId}/
    task.json                      # author payload (+ materialGateRevise if present)
    material-spec.json
    material-review-marker.json    # optional; in-session review pass
    AUTHOR_BRIEF.md                # optional bootstrap
    SKILLS_SUMMARY.md
    preview.mp4 / draft.json / …   # session scratch residuals
  material-reviews/{slotId}/
    report.json                    # approved, issues, reviewInputs, trace, reviewPhase
    frames/                        # optional extracted frames
  generated/{actionId}/
    material-spec.json             # promoted/render-side copy
    composition/                   # HF project
    *.mp4 / preview
  narration/ …                     # assembly stage (not author)
```

**actionId vs slotId：** plan `completionActions[].id` 常为 `action-slot-5`；scratch 目录名用 **slotId**（`slot-5`）。对照 `generation-plan.json`。

## ACP author traces

```text
{root}/logs/composition-author/acp/{runId}/
  session.json
  prompt.json
  tool_calls.jsonl
  outcome.json
```

| File | Key fields |
|------|------------|
| `session.json` | `agentCommand`, `scratchDir`, `inSessionReviewEnabled`, `reviewMaxRounds`, `dialogueSafetyMax`, `acpTimeoutSec`, `compositionTemplate`, `observabilityRunId`, `acpProtocolSessionId` |
| `prompt.json` | `system`, `user` |
| `tool_calls.jsonl` | one JSON per line: `session_update`, `permission`, `policy_violation`, … |
| `outcome.json` | `valid`, `totalLatencyMs`, `validationErrors`, `generationId`, `taskId`, `agentDiagnostics` (`mcpToolsAvailable`, exit code, stderr tail) |

`runId` = 目录名 = 12-char hex（创建 session 一次）。

## ReAct author traces

```text
{root}/logs/composition-author/{runId}/
  # turns / outcome / session — see FileReactTraceRecorder output
```

**Diff：** ReAct **没有**中间的 `acp/` 路径段。  
Agent-run promptVersion 常见：`composition-react-bootstrap` vs ACP `composition-acp-v1`。

## Observability mirrors

```text
{root}/logs/agent-runs/{uuid}.json
{root}/logs/model-calls/{uuid}.json
{root}/logs/tool-runs/{id}.json     # acp-*.json, review_material_preview, …
```

Filter fields: `generationId`, `taskId`, `agentName`, `profile`（`vision` / `video_understanding` / `text`）, `toolName`（`acp_session_start` / `acp_turn_lint_gate` / `acp_session_end` / `review_material_preview`）。

API（可选）：

```http
GET /api/generations/{generationId}/agent-runs
GET /api/generations/{generationId}/model-calls
GET /api/generations/{generationId}/material-review
```

## Env knobs that change what you see

| Env | Effect on logs |
|-----|----------------|
| `VIDEOMAKER_COMPOSITION_AUTHOR_BACKEND=acp\|react` | which trace tree exists |
| `VIDEOMAKER_COMPOSITION_ACP_AGENT` | Cursor vs Claude vs Codex in session |
| `VIDEOMAKER_MATERIAL_REVIEW_ACP_IN_SESSION` | first-gen worker post-turn vision |
| `VIDEOMAKER_MATERIAL_REVIEW_ACP_IN_SESSION_REVISE` | gate revise in-session vision |
| `VIDEOMAKER_MATERIAL_REVIEW_GATE_LLM` | if no marker, gate finalize runs LLM |
| `VIDEOMAKER_MATERIAL_REVIEW_MAX_ROUNDS` | billed vision cap per slot |
| `VIDEOMAKER_OBSERVABILITY_CAPTURE` | fullness of tool/model payloads |

## How to find the right run without traceId

1. Restrict time window from workbench/SSE timestamps.  
2. List `logs/composition-author/acp/*/outcome.json` by `recordedAt` desc.  
3. Match `generationId` (± `taskId`).  
4. Confirm `session.json.scratchDir` ends with `acp-author/{slotId}`.  
5. Cross-check `tool-runs` `acp_session_*` with same `observabilityRunId` / time.
