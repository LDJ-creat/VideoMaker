# P1 Observability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose **ModelGateway readiness** (P1 required for web diagnostics), Agent run history API, and optional Langfuse behind `ObservabilitySink` — without making external observability authoritative for task recovery.

**Architecture:** Worker `AgentRunStore` + API read routes. `GET /api/settings/model-gateway` reads worker/env configuration **without secrets** (implemented in API service from env mirror or shared config module). Langfuse optional.

**Tech Stack:** FastAPI, Python settings, optional Langfuse SDK, AgentRunner.

---

## Session Context

**Depends on:** `feature/p1-agent-orchestration` (AgentRunStore); **model-gateway status** also depends on `feature/p1-model-gateway` env layout.

**Master plan:** §15.

**Branch:** `feature/p1-observability`

**Execute:**

- **Task 4–5 (model-gateway status) early** — can merge before full observability if web Phase B blocked; minimum viable: status route only.
- Full plan after multi-variant merge recommended.

**Downstream:** `p1-web-workbench` Phase B Task 7 (ModelGatewayStatusPanel), Task 11 (AgentRunsDrawer).

---

## Files Allowed To Change

**Create:**

```text
services/worker/app/observability/__init__.py
services/worker/app/observability/sink.py
services/worker/app/observability/langfuse_sink.py
services/api/app/routers/agent_runs.py
services/api/app/services/model_gateway_status.py
services/api/tests/test_agent_runs_route.py
services/api/tests/test_model_gateway_status_route.py
services/worker/tests/test_observability_sink.py
```

**Modify:**

```text
services/worker/app/agents/runner.py
services/api/app/routers/settings.py          # add model-gateway route here OR extend
services/api/app/main.py
services/worker/pyproject.toml
```

**Out of scope:** Storing API keys in SQLite; exposing secrets to frontend; Langfuse as task authority.

---

## ObservabilitySink Interface

```python
class ObservabilitySink(Protocol):
    def record_agent_run(self, log: dict) -> None: ...
    def record_tool_run(self, log: dict) -> None: ...
```

Implementations: `LocalFileSink` (default), optional `LangfuseSink` if `LANGFUSE_ENABLED=true`.

---

## API — Model Gateway Status (P1 REQUIRED)

```http
GET /api/settings/model-gateway
```

**Response shape (locked):**

```json
{
  "fixtureMode": false,
  "providers": {
    "text": { "configured": true, "model": "gpt-4o", "driver": "openai_compatible" },
    "vision": { "configured": true, "model": "gpt-4o", "driver": "openai_compatible" },
    "tts": { "configured": false, "model": null, "driver": "openai_compatible" },
    "image": { "configured": true, "model": "dall-e-3", "driver": "openai_compatible" },
    "video": { "configured": false, "model": null, "driver": "generic_job" }
  }
}
```

**Rules:**

1. `configured: true` iff required env vars present for that provider (same rules as worker `GatewayConfig`).
2. Never return `api_key`, `apiKey`, or raw env values.
3. `fixtureMode` from `VIDEOMAKER_FIXTURE_MODE` (worker) — API reads same env or queries worker health; prefer **shared env read in API** for simplicity.
4. If vision env unset but text configured, report vision as configured with text fallback model name.

Implement in `services/api/app/services/model_gateway_status.py` duplicating env key names from worker `gateway/config.py` (keep list in sync — comment cross-reference).

**Tests:** `test_model_gateway_status_route.py` with monkeypatched env.

---

## API — Agent Runs

```http
GET /api/generations/{generation_id}/agent-runs
```

Response:

```json
{
  "runs": [
    {
      "id": "run-1",
      "agentName": "structure_analyst",
      "model": "gpt-4o",
      "promptVersion": "a1b2c3d4",
      "outputValid": true,
      "latencyMs": 1200,
      "createdAt": "2026-05-29T12:00:00Z"
    }
  ]
}
```

Read from filesystem logs under project/generation — not Langfuse.

---

## CritiqueReviser (Optional P1)

Feature flag `VIDEOMAKER_ENABLE_CRITIQUE=false` default. Out of critical path.

---

## Task Checklist

- [ ] **Task 1:** ObservabilitySink protocol + LocalFileSink wrapper test.
- [ ] **Task 2:** Wire AgentRunner to MultiSink.
- [ ] **Task 3:** agent-runs API route + test with temp log files.
- [ ] **Task 4:** **REQUIRED** `GET /api/settings/model-gateway` + `model_gateway_status.py` + tests.
- [ ] **Task 5:** LangfuseSink guarded import; skip if package missing (optional).
- [ ] **Task 6:** Register routes in `settings.py` or `main.py`; document env vars in API docstring.

---

## Verification

```powershell
cd services/api
python -m pytest tests/test_model_gateway_status_route.py tests/test_agent_runs_route.py -v

cd ../worker
python -m pytest tests/test_observability_sink.py -v
```

---

## Acceptance Criteria

1. Model gateway status returns configured flags without secrets — **required for web Task 7**.
2. Agent runs queryable for generations with logs on disk.
3. Langfuse off by default; missing keys do not break pipeline.
4. Task recovery still SQLite + artifacts only.

---

## Commit Message

```text
feat(api): model gateway status and agent run observability routes
```
