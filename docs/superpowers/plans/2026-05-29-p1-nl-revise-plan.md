# P1 Natural Language Revise Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement NL revise: user instruction → EditIntentParser Agent → IntentApplier → partial pipeline re-run → new generationId.

**Architecture:** API route `POST /api/generations/{generationId}/revise`. Worker `revise_pipeline.py` loads source artifacts, parses intents, computes affected stages, forks new generation directory, runs from first affected stage to render.

**Tech Stack:** EditIntent schema, AgentRunner, existing checkpoint system.

---

## Session Context

**Depends on:**

1. `feature/p1-agent-orchestration`
2. `feature/p1-multi-variant-generation` recommended (stable generation artifacts)
3. Material completion wired (revise may re-trigger material stages)

**Master plan:** §10.

**Branch:** `feature/p1-nl-revise`

---

## Files Allowed To Change

**Create:**

```text
services/worker/app/agents/edit_intent_parser.py
services/worker/app/pipelines/revise_pipeline.py
services/worker/app/pipelines/intent_applier.py
services/worker/tests/fixtures/agents/edit_intent_parser.json
services/worker/tests/test_intent_applier.py
services/worker/tests/test_revise_pipeline.py
packages/prompts/agents/edit_intent_parser.md
services/api/tests/test_revise_generation.py
```

**Modify:**

```text
services/api/app/routers/generations.py   # or projects.py — add revise route
services/worker/app/pipelines/p0_demo_pipeline.py   # dispatch revise task type
```

**Out of scope:** Web UI (web plan), new EditIntent operations beyond schema enum (extend only if tests require).

---

## API

```http
POST /api/generations/{generation_id}/revise
Content-Type: application/json

{ "instruction": "开头更抓人一些，字幕少一点" }
```

**Response 202:**

```json
{
  "sourceGenerationId": "gen-src",
  "generationId": "gen-new",
  "taskId": "task-new",
  "intents": [
    {
      "target": "generation_plan.storyboard",
      "operation": "adjust_hook",
      "params": { "strength": "high" },
      "rationale": "用户希望开头更抓人"
    },
    {
      "target": "generation_plan.packaging",
      "operation": "reduce_subtitles",
      "params": {},
      "rationale": "用户希望减少字幕"
    }
  ]
}
```

Persist intents to `generations/{newId}/edit-intent.json`.

---

## EditIntentParser Agent

Task: `edit_intent_parser`  
Schema: `edit-intent`

Inputs:

```json
{
  "instruction": "...",
  "sourceSummary": {
    "variant": "high_click",
    "storyboardSceneCount": 8,
    "timelineDurationSec": 30,
    "packagingDensity": "medium"
  }
}
```

Prompt maps Chinese/English colloquial phrases to operations (examples in prompt file).

---

## IntentApplier

```python
def compute_affected_stages(intents: list[EditIntentItem]) -> list[str]:
```

| Operation | Minimum affected stages |
| --- | --- |
| adjust_hook | storyboard, material, packaging, timeline, render |
| reduce_subtitles / increase_subtitles | packaging, timeline, render |
| reorder_selling_points | storyboard, material, timeline, render |
| change_pace | storyboard, timeline, render |
| change_packaging_style | packaging, material, timeline, render |
| adjust_cta | storyboard, packaging, timeline, render |

Return ordered stage list for checkpoint resume.

```python
def apply_intents_to_context(intents, source_plan, source_timeline) -> ReviseContext:
```

Sets generation_params overrides consumed by Agents (e.g. `hookStrength: high`).

---

## Revise Pipeline

```text
1. Load source generation-plan.json, render-timeline.json, gap-report.json
2. Parse instruction → edit-intent.json (sync in API before task dispatch OR first worker stage parsing_edit_intent)
3. Clone metadata → new generationId (SQLite + filesystem)
4. Copy artifacts up to stage before first affected
5. applying_edit_intent → merge overrides
6. Re-run pipeline stages from first affected
7. Never mutate source generation directory
```

Task stages: `parsing_edit_intent`, `applying_edit_intent`, then normal generation stages.

---

## Task Checklist

- [ ] **Task 1:** edit_intent_parser prompt + fixture.
- [ ] **Task 2:** intent_applier unit tests for stage computation.
- [ ] **Task 3:** revise API route + test.
- [ ] **Task 4:** revise_pipeline integration test with fixtures (no render if HF missing — mock render backend).
- [ ] **Task 5:** Verify source generation unchanged after revise.

---

## Verification

```powershell
cd services/api
python -m pytest tests/test_revise_generation.py -v

cd ../worker
python -m pytest tests/test_intent_applier.py tests/test_revise_pipeline.py -v
```

---

## Acceptance Criteria

1. Revise creates new generationId and taskId.
2. Edit intents persisted and returned in API response.
3. Source generation artifacts byte-identical before/after revise.
4. adjust_hook + reduce_subtitles fixture triggers packaging + storyboard stages.

---

## Commit Message

```text
feat: natural language generation revise with EditIntent pipeline
```
