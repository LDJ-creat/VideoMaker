# P1 Asset Understanding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enrich `AssetInventory` with LLM-driven brief analysis and visual understanding of user-uploaded assets: tags, highlight scores, and hook/mid/cta moment recommendations.

**Architecture:** `ContentStrategist` Agent processes `UserBrief` → `ContentFact[]`. `AssetVisionAnalyzer` (module, may use vision gateway) processes each video/image asset → updates `candidateMoments` and asset tags. Runs in generation pipeline before SlotMapper.

**Tech Stack:** AgentRunner, vision profile for images/keyframes, OpenCV metadata from P0 asset analysis.

---

## Session Context

**Depends on:** `feature/p1-agent-orchestration` merged.

**Master plan:** §6.4 P1 extensions, contracts `CandidateMoment` fields.

**Branch:** `feature/p1-asset-understanding`

**Parallel with:** `feature/p1-llm-structure-analysis`, `feature/p1-semantic-mapping-gap`.

---

## Files Allowed To Change

**Create:**

```text
services/worker/app/agents/content_strategist.py
services/worker/app/pipelines/asset_understanding.py
services/worker/tests/fixtures/agents/content_strategist.json
services/worker/tests/test_asset_understanding.py
packages/prompts/agents/content_strategist.md
```

**Modify:**

```text
services/worker/app/pipelines/generation_pipeline.py
services/worker/app/pipelines/p0_demo_pipeline.py   # call asset understanding stage
packages/prompts/agents/content_strategist.md
```

**Out of scope:** Slot matching, AIGC, API new routes, web UI.

---

## Pipeline Stage

Insert after `analyzing_assets` per-task stage:

```text
1. Load user brief + asset metadata from API/storage
2. ContentStrategist → { extractedFacts: ContentFact[] }
3. For each video asset:
   a. Use existing shot boundaries from asset analysis JSON if present
   b. Else extract shots via OpenCVTool (reuse P0)
   c. Score moments (algorithm):
      highlightScore = 0.4 * motionScore + 0.3 * sharpnessScore + 0.3 * centerSubjectScore
   d. Vision LLM on top 3 moments → visualTags + suggestedSegmentRoles
4. Merge into AssetInventory JSON; validate schema
5. Checkpoint: asset-inventory.json
```

---

## ContentStrategist Output Shape

Validate merged inventory against `asset-inventory` schema. Agent output intermediate:

```json
{
  "extractedFacts": [
    { "id": "fact-1", "text": "...", "category": "selling_point", "confidence": 0.9 }
  ],
  "toneSummary": "..."
}
```

Pipeline merges into full `AssetInventory` preserving existing `assets[]` from API.

---

## Vision Moment Analysis

For each candidate moment (top 5 by highlightScore):

**Input:** keyframe base64 + transcript snippet if video has audio.

**Output (per moment):**

```json
{
  "momentId": "moment-1",
  "visualTags": ["product", "close-up"],
  "suggestedSegmentRoles": ["hook"],
  "description": "手持产品特写"
}
```

Use task key `asset_moment_vision` with schema fragment validated in test (or small json schema file `asset-moment-vision.schema.json` in contracts if needed — prefer inline validation in plan implementation to avoid blocking on contracts if already merged).

---

## Prompt: content_strategist.md

- Input: UserBrief fields (topic, productName, sellingPoints, mustMention, avoidMention).
- Output: structured facts, no marketing fluff outside brief.
- Respect `avoidMention`.

---

## Task Checklist

- [ ] **Task 1:** Create prompt + fixture.
- [ ] **Task 2:** Implement `run_content_strategist`.
- [ ] **Task 3:** Implement `asset_understanding.py` with highlight scoring (deterministic scores — not semantic fallback).
- [ ] **Task 4:** Wire into generation pipeline; emit TaskEvent `analyzing_assets`.
- [ ] **Task 5:** Tests: inventory contains `visualTags` and `suggestedSegmentRoles` on at least one moment.

---

## Verification

```powershell
cd services/worker
python -m pytest tests/test_asset_understanding.py tests/test_generation_plan.py -v
```

---

## Acceptance Criteria

1. Generation pipeline produces enriched `AssetInventory` before slot mapping.
2. Video assets have ≥1 `candidateMoment` when shots exist.
3. Content facts derived from brief via Agent fixture/live path.
4. Schema-valid `asset-inventory`.

---

## Commit Message

```text
feat(worker): LLM asset understanding with highlight moments
```
