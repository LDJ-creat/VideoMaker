# P1 Semantic Mapping And Gap Planning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement LLM-driven SlotMapper and GapPlanner with natural-language `matchReason`, P1 provider selection algorithm, and hard post-validation of type/duration constraints.

**Architecture:** SlotMapper Agent outputs slot matches; Python post-check enforces thresholds. GapPlanner Agent assigns `CompletionAction.provider` using master plan §8.4; quota tracker deferred to aigc plan but stub counter interface defined here.

**Tech Stack:** AgentRunner, schemas `gap-report`, variant `agentOverrides` from registry (read overrides for gap_planner).

---

## Session Context

**Depends on:**

1. `feature/p1-agent-orchestration`
2. `feature/p1-asset-understanding` (recommended merge first for richer inventory tests)

**Master plan:** §8.4 provider selection.

**Branch:** `feature/p1-semantic-mapping-gap`

**Parallel with:** structure analysis, asset understanding.

---

## Files Allowed To Change

**Create:**

```text
services/worker/app/agents/slot_mapper.py
services/worker/app/agents/gap_planner.py
services/worker/app/pipelines/gap_selection.py
services/worker/tests/fixtures/agents/gap_planner.json
services/worker/tests/test_gap_selection.py
services/worker/tests/test_slot_mapper_agent.py
```

**Modify:**

```text
services/worker/app/pipelines/generation_pipeline.py
packages/prompts/agents/slot_mapper.md
packages/prompts/agents/gap_planner.md
```

**Out of scope:** Executing AIGC tools (aigc plan), HyperFrames material render, API variants.

---

## SlotMapper

**Inputs:**

```json
{
  "videoStructure": { "...": "VideoStructure" },
  "assetInventory": { "...": "AssetInventory" },
  "variantOverrides": { }
}
```

**Agent output** (merge into gap-report):

```json
{
  "slotMatches": [
    {
      "slotId": "slot-hook-visual",
      "assetId": "asset-1",
      "momentId": "moment-2",
      "matchScore": 0.71,
      "matchReason": "用户素材包含产品特写，与 hook_visual 意图一致"
    }
  ]
}
```

**Post-validation (`slot_mapper.py`):**

1. Recompute type/duration score in Python; if Agent score differs by >0.25, clamp and append note to matchReason.
2. Matches with score ≥0.62 → matched; 0.38–0.62 → weak (move to weakSlots in gap report builder); <0.38 → treat as unmatched.

---

## GapPlanner

**Inputs:** structure, inventory, slotMatches, weak/unmatched slots, `variantOverrides.gap_planner`.

**Output:** full `gap-report` schema including `missingSlots`, `weakSlots`, `summary`.

Each missing/weak slot includes `suggestedFixes` as provider names and embedded `CompletionAction` drafts:

```json
{
  "slotId": "slot-product-closeup",
  "reason": "无商品特写素材",
  "impact": "high",
  "suggestedFixes": ["image_generation"],
  "completionAction": {
    "provider": "image_generation",
    "rationale": "must_have hook_visual 需要写实商品画面"
  }
}
```

---

## Provider Selection (`gap_selection.py`)

Implement deterministic **provider picker** (not LLM fallback — this is business rules executing GapPlanner suggestions):

```python
def select_provider(
    slot: StructureSlot,
    *,
    weak_match: SlotMatch | None,
    quota: VideoGenQuota,
    variant_overrides: dict,
) -> str:
```

Algorithm (implemented in `gap_selection.py`):

1. Packaging roles (`hook_text`, `benefit_card`, `comparison`) → `hyperframes_material`
2. weak_match score ≥0.38:
   - matched asset `type=video` → `asset_reuse` (ffmpeg trim)
   - matched asset `type=image` on visual slot (`hook_visual`, `product_closeup`, `usage_scene`) + per-slot quota → `video_generation` (i2v); else `image_generation`
3. Visual slot without weak video match: per-slot quota → `video_generation` (t2v); else `image_generation` (may chain `hyperframes_material` for motion)
4. `scriptIntent` needs VO → `tts`
5. else → `hyperframes_material`

**VideoGenQuota:** per slot up to `VIDEOMAKER_VIDEO_GEN_MAX_PER_SLOT` (default 1); generation cap `max_slots` from visual weak/missing slots (`from_structure`). Legacy checkpoint `used`/`maxCalls` migrates without blocking new slot IDs.

GapPlanner inputs include `videoGenMaxSlots` / `videoGenMaxPerSlot`. `asset_reuse` must not be used for image assets.

---

## Variant Overrides

Load from `packages/contracts/variants/registry.yaml` via Python (read YAML in worker or duplicate minimal loader in `services/worker/app/config/variants.py`).

Pass `agentOverrides.gap_planner` into GapPlanner inputs.

---

## Task Checklist

- [ ] **Task 1:** slot_mapper agent + post-validation tests.
- [ ] **Task 2:** gap_planner agent + fixture full gap-report.
- [ ] **Task 3:** gap_selection.py unit tests for all branches.
- [ ] **Task 4:** Wire stages `mapping_slots`, `planning_completion`.
- [ ] **Task 5:** Update prompts with provider list and Chinese matchReason examples.

---

## Verification

```powershell
cd services/worker
python -m pytest tests/test_gap_selection.py tests/test_slot_mapper_agent.py tests/test_generation_plan.py -v
```

---

## Acceptance Criteria

1. GapReport includes provider per missing slot with rationale.
2. Provider selection matches §8.4 for fixture scenarios (table-driven tests).
3. matchReason present on every SlotMatch.
4. No deterministic Jaccard code remains in generation_pipeline.

---

## Commit Message

```text
feat(worker): semantic SlotMapper and GapPlanner with provider selection
```
