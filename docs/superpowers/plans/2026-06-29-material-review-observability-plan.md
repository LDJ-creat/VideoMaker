# Material Review Observability Plan

**Date:** 2026-06-29  
**Status:** Implemented  
**Related:** [Material Review Gate](./2026-06-29-material-review-gate-plan.md)

## Goal

Align material review LLM calls with the existing observability stack (`model-calls`, `agent-runs`, `tool-runs`) and link business artifacts (`material-reviews/{slotId}/report.json`) via optional `trace` fields.

## Behavior

When `material_reviewer` runs (video / vision / text_only routes):

1. `setup_material_review_observability` attaches `LocalFileSink` (+ Langfuse when enabled) to the gateway with `slotId`, `taskId`, `generationId`.
2. `ModelGateway.complete_json_messages` records `logs/model-calls/*.json` with `agentName=material_reviewer`.
3. Video/vision paths also write `logs/agent-runs/*.json` via `record_material_reviewer_agent_run`.
4. Text-only path uses `AgentRunner` agent-run + model-call (no duplicate agent-run).
5. Author session `review_material_preview` writes `logs/tool-runs/review_material_preview-*.json`.
6. ACP MCP subprocess receives `VM_ACP_OBSERVABILITY_RUN_ID` for parent session linkage.
7. `report.json` includes optional `trace`: `{ reviewRoute, modelCallId, agentRunId, promptVersion, parentObservabilityRunId }`.

Skipped / hard_gate paths set `trace.reviewRoute` only; no model-call.

## Key modules

| Module | Role |
|--------|------|
| `services/worker/app/observability/material_review_recorder.py` | Setup sink, agent-run, tool-run, trace builders |
| `services/composition/composition/material_review/preview.py` | `run_review_via_worker` observability wiring |
| `services/worker/app/pipelines/material_review.py` | `run_slot_review` trace + LLM session |
| `packages/contracts/schemas/material-review-report.schema.json` | `trace` object |

## Env

Uses existing `VIDEOMAKER_OBSERVABILITY_CAPTURE` (`full` \| `summary` \| `off`).  
ACP parent link: `VM_ACP_OBSERVABILITY_RUN_ID` (set by worker ACP author spawn).

## Verification

```powershell
cd services/worker
python -m pytest tests/test_material_review_observability.py -q

cd services/composition
python -m pytest tests/test_review_via_worker_observability.py -q
```

See `docs/demos/material-review-gate-e2e-checklist.md` § Observability.
