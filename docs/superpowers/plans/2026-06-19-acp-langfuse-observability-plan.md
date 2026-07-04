# ACP Langfuse Observability Plan

**Status:** implemented  
**Parent:** [`2026-06-19-composition-acp-author-plan.md`](2026-06-19-composition-acp-author-plan.md)  
**E2E:** [`docs/demos/composition-acp-author-e2e-checklist.md`](../demos/composition-acp-author-e2e-checklist.md), [`docs/demos/langfuse-observability-e2e-checklist.md`](../demos/langfuse-observability-e2e-checklist.md)

## Goal

Bridge ACP external agent material author sessions into the shared ObservabilitySink (local `tool-runs` + optional Langfuse spans), without faking ModelGateway `model-call` records.

## Modules

| Module | Role |
|--------|------|
| [`services/worker/app/observability/acp_author_recorder.py`](../../services/worker/app/observability/acp_author_recorder.py) | `AcpAuthorObservabilityContext`, session/repair/lint/client events |
| [`services/worker/app/composition/acp/author.py`](../../services/worker/app/composition/acp/author.py) | Session lifecycle hooks |
| [`services/worker/app/composition/acp/headless_client.py`](../../services/worker/app/composition/acp/headless_client.py) | Permission / session_update / terminal / ext_notification |
| [`services/worker/app/providers/hyperframes_material_provider.py`](../../services/worker/app/providers/hyperframes_material_provider.py) | Wire sink + fix `agent_run.model` |
| [`services/worker/app/observability/langfuse_sink.py`](../../services/worker/app/observability/langfuse_sink.py) | ACP metadata on agent/tool spans |

## Env

| Env | Default |
|-----|---------|
| `VIDEOMAKER_ACP_OBSERVABILITY_MAX_SESSION_UPDATES` | `40` |

## Verification

```powershell
cd services/worker
python -m pytest tests/test_acp_observability.py tests/test_acp_author.py -q
python -m pytest tests/test_hyperframes_material_provider.py::test_hyperframes_provider_uses_acp_author_backend -q
```

## Out of scope

- External agent token usage parsing
- `GET /api/.../tool-runs` API
- Workbench UI for ACP spans
