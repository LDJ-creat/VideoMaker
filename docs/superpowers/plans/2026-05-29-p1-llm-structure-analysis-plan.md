# P1 LLM Structure Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade StructureAnalyst to production-quality LLM structure extraction: multimodal keyframe inputs, evidence enforcement, rhythm facts from algorithm layer, and post-validation — replacing minimal fixture-only behavior from agent-orchestration.

**Architecture:** Perception stages unchanged (`sample_pipeline`). New module `structure_inputs.py` builds Agent payload. StructureAnalyst uses `profile=vision` when keyframes present. Post-validator `structure_validator.py` rejects outputs missing evidence.

**Tech Stack:** ModelGateway vision chat, base64 image encoding, JSON Schema `video-structure`.

---

## Session Context

**Depends on:** `feature/p1-agent-orchestration` merged (AgentRunner + StructureAnalyst stub exists).

**Master plan:** §7.1, §15 Task 4.

**Branch:** `feature/p1-llm-structure-analysis`

**Parallel with:** `feature/p1-asset-understanding`, `feature/p1-semantic-mapping-gap` (after orchestration merge).

---

## Files Allowed To Change

**Create:**

```text
services/worker/app/agents/structure_inputs.py
services/worker/app/validation/structure_validator.py
services/worker/tests/test_structure_inputs.py
services/worker/tests/test_structure_validator.py
services/worker/tests/test_structure_analyst_agent.py
```

**Modify:**

```text
services/worker/app/agents/structure_analyst.py
packages/prompts/agents/structure_analyst.md
services/worker/app/pipelines/p0_demo_pipeline.py   # stage events only if needed
```

**Out of scope:** API route changes, web UI (separate plan), deleting generation rules.

---

## Input Packaging Algorithm

`build_structure_analyst_inputs(analysis: dict, *, max_keyframes: int = 8) -> dict`:

1. Copy `metadata`, `transcript`, `shots` verbatim from `sample-analysis.json`.
2. Select keyframes: at most one per shot, prefer highest `score`; cap at `max_keyframes` evenly spaced across timeline.
3. For each keyframe, read image bytes from artifact path under project storage; encode base64; add:

```json
{
  "shotId": "shot-1",
  "timeSec": 0.7,
  "imageBase64": "...",
  "mimeType": "image/jpeg"
}
```

4. Precompute rhythm facts (algorithm, not LLM):

```python
rhythm_facts = {
  "shotCount": len(shots),
  "avgShotDurationSec": ...,
  "tempoHint": "fast" | "medium" | "slow" | "mixed"  # CV coefficient rule from P0 plan
}
```

5. Pass `rhythmFacts` in inputs; prompt instructs LLM to use as constraints for `RhythmProfile`.

---

## Vision Gateway Message Format

In `structure_analyst.py`, when keyframes non-empty:

```python
messages = [
  {"role": "system", "content": system_prompt},
  {"role": "user", "content": [
    {"type": "text", "text": json.dumps(text_payload)},
    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
    ...
  ]}
]
gateway.complete_json(..., profile="vision")
```

Implement vision message builder in gateway or agent — document single location.

---

## Post-Validation Rules (`structure_validator.py`)

After schema validation:

1. Every `narrative.segments[]` must have ≥1 `evidence[]` entry referencing transcript time range or keyframe path.
2. Every `slots[]` must reference valid `segmentId`.
3. `confidence` must be 0–1.
4. If segment role is `cta`, final segment `endSec` must be within 15% of video duration from end.
5. On failure: raise `StructureValidationError` → task fails (optional single repair call: re-prompt with error list — max 1 retry).

- [ ] Test each rule with invalid fixture.

---

## Prompt Updates (`structure_analyst.md`)

Must include:

- Copyright boundary: migrate structure method, do not copy script text.
- Map roles: hook, problem, solution, proof, benefit, comparison, cta, transition.
- Require `evidence` array per segment with `source: transcript|shot|keyframe`.
- Use `rhythmFacts` for `RhythmProfile.shotBoundaries` alignment.

---

## Task Checklist

- [ ] **Task 1:** `structure_inputs.py` + tests (no network).
- [ ] **Task 2:** `structure_validator.py` + tests.
- [ ] **Task 3:** Wire vision profile in StructureAnalyst.
- [ ] **Task 4:** Integration test with fixture gateway returning valid structure; validator passes.
- [ ] **Task 5:** Update agent fixture JSON to include evidence arrays.

---

## Verification

```powershell
cd services/worker
python -m pytest tests/test_structure_inputs.py tests/test_structure_validator.py tests/test_structure_analyst_agent.py tests/test_p0_demo_pipeline.py -v
```

---

## Acceptance Criteria

1. StructureAnalyst inputs include base64 keyframes when available.
2. Invalid evidence triggers failure (or one repair then failure).
3. `GET /api/samples/{id}/structure` returns enriched VideoStructure (API unchanged).
4. Rhythm shot boundaries remain consistent with analysis shots within tolerance ±0.5s.

---

## Commit Message

```text
feat(worker): multimodal StructureAnalyst with evidence validation
```
