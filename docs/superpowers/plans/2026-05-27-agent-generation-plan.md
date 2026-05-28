# Agent Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the contract-driven Agent generation pipeline that turns sample analysis artifacts and user brief/assets into `VideoStructure`, `AssetInventory`, `GapReport`, and `GenerationPlan`.

**Architecture:** Implement deterministic local planners first, with LLM adapters behind interfaces. Tests should use fixtures and fake model outputs. All model outputs must be schema-validated before use.

**Tech Stack:** Python 3.11, pytest, JSON Schema validation, prompt markdown files, shared contracts as schema files.

---

## Required P0 Outputs

This module must produce four contract-valid artifacts:

- `video-structure.json`: `VideoStructure` from `sample-analysis.json`.
- `asset-inventory.json`: `AssetInventory` from user brief and uploaded asset metadata.
- `gap-report.json`: `GapReport` from slot mapping.
- `generation-plan.json`: `GenerationPlan` including storyboard, completion actions, packaging plan, and `RenderTimeline`.

The implementation must work without external model access in fixture mode. LLM-backed behavior is allowed only behind `LLMTool`; deterministic local behavior is required for tests and demo reliability.

## Deterministic Structure Extraction Rules

Input shape expected from worker `sample-analysis.json`:

```json
{
  "metadata": {"durationSec": 30, "width": 1080, "height": 1920, "fps": 30, "hasAudio": true},
  "transcript": [{"startSec": 0.2, "endSec": 2.1, "text": "...", "confidence": 0.92}],
  "shots": [{"startSec": 0, "endSec": 1.4, "confidence": 0.8, "changeReason": "scene_change"}],
  "keyframes": [{"shotId": "shot-1", "timeSec": 0.7, "path": "...", "score": 0.81}]
}
```

P0 local structure extraction algorithm:

1. Build `RhythmProfile` directly from `shots`: shot count, average shot duration, tempo, shot boundaries, and beat points.
2. Classify tempo as `fast` when average shot duration `< 1.2s`, `medium` when `1.2s-2.8s`, `slow` when `> 2.8s`, and `mixed` when shot duration coefficient of variation is above `0.65`.
3. Create narrative segments from time ranges:
   - `hook`: `0s` to `min(3s, 15% duration)`.
   - `problem` or `benefit`: next 25% of duration based on transcript keywords.
   - `solution` or `proof`: middle 40% of duration.
   - `cta`: final `max(2s, 15% duration)`.
4. If transcript has CTA keywords such as `buy`, `click`, `order`, `learn more`, `下单`, `点击`, `购买`, force final segment role to `cta`.
5. Create `StructureSlot` entries from segments:
   - `hook` -> `hook_visual` and `hook_text`.
   - `benefit` -> `benefit_card`.
   - `solution` -> `usage_scene`.
   - `proof` -> `proof`.
   - `comparison` -> `comparison`.
   - `cta` -> `cta`.
6. Attach evidence to each segment and slot from transcript overlap, shot boundaries, and keyframe paths.
7. Use `packaging.visualDensity = "high"` if transcript text length per second is above `8`, `medium` if above `3`, otherwise `low`.

Keyword hints:

```text
problem: pain, difficult, tired, expensive, slow, trouble, 痛点, 困扰, 麻烦, 太贵
benefit: save, faster, better, improve, easy, 省, 快, 提升, 方便
proof: real, test, result, compare, before, after, 真实, 实测, 对比, 效果
cta: buy, click, order, follow, learn more, 下单, 点击, 关注, 购买
```

## Slot Matching Algorithm

Match every `StructureSlot` against `AssetInventory.assets` and `candidateMoments`.

Score:

```text
typeScore = 1.0 if asset type satisfies requiredAssetType, 0.5 if text can cover visual through packaging, otherwise 0
semanticScore = Jaccard overlap between normalized slot intent tokens and asset tags/facts
durationScore = min(1.0, candidateDuration / slotDuration) for video moments, 0.7 for images, 0.6 for text
importanceWeight = 1.0 for must_have, 0.8 for recommended, 0.5 for optional
matchScore = (typeScore * 0.35 + semanticScore * 0.4 + durationScore * 0.15) * importanceWeight
```

Thresholds:

- `matchScore >= 0.62`: matched.
- `0.38 <= matchScore < 0.62`: weak slot.
- `< 0.38`: missing slot.

Tie-breakers:

1. Prefer user-uploaded video over generated or text substitutes for visual slots.
2. Prefer moments whose duration is closest to slot duration.
3. Prefer assets not already used by a higher-importance slot.

## Gap Completion Strategy Rules

Choose P0 completion strategies deterministically:

- Use `asset_reuse` when a weak video/image match exists and the slot is visual.
- Use `packaging_completion` when the slot role is `benefit_card`, `hook_text`, `comparison`, or visualDensity is high.
- Use `text_completion` when user brief facts can express the slot without new visuals.
- Do not use `image_generation`, `video_generation`, or `tts` in P0 unless a later plan explicitly enables those providers.

Each missing or weak slot must include:

```json
{
  "slotId": "...",
  "reason": "No uploaded asset shows product close-up",
  "impact": "high",
  "suggestedFixes": ["packaging_completion", "text_completion"]
}
```

## GenerationPlan And RenderTimeline Rules

Storyboard generation:

- One `StoryboardScene` per `StructureSlot`.
- Preserve slot timing from `VideoStructure` unless a completion action requires text/card duration adjustment.
- `source` must be one of `user_asset`, `text_completion`, `packaging_completion`, `asset_reuse`, `generated`.

RenderTimeline generation:

- Always create tracks in this order: `video`, `image`, `text`, `effect`, `transition`, `voiceover`, `bgm`.
- For matched video/image slots, create media clips with `sourceRef` pointing to asset or moment IDs.
- For text/package completion, create text clips with `content` and `styleRef`.
- For transitions, create short clips at slot boundaries, default duration `0.18s`.
- Timeline duration must equal the max `endSec` across storyboard scenes.

## Scope And Boundaries

Branch/worktree:

```powershell
git worktree add .worktrees/agent-generation -b feature/agent-generation main
```

Allowed to create/modify:

- `services/worker/app/agents/**`
- `services/worker/app/pipelines/structure_pipeline.py`
- `services/worker/app/pipelines/generation_pipeline.py`
- `services/worker/app/tools/llm_tool.py`
- `services/worker/tests/**`
- `packages/prompts/**`
- `docs/superpowers/plans/2026-05-27-agent-generation-plan.md`

Do not modify:

- `packages/contracts/**` unless explicitly stopped and approved
- `apps/web/**`
- `services/api/**`

## Task 1: Schema Loading And Validation

**Files:**
- Create: `services/worker/app/validation/schema_loader.py`
- Create: `services/worker/tests/test_schema_loader.py`

- [ ] Write failing tests that load every schema from `packages/contracts/schemas`.
- [ ] Implement schema discovery from repo root.
- [ ] Implement `validate_contract(name, payload)` returning structured validation errors.
- [ ] Run `python -m pytest`.
- [ ] Commit: `feat(agent): add contract schema validation`.

## Task 2: LLM Tool Boundary

**Files:**
- Create: `services/worker/app/tools/llm_tool.py`
- Create: `services/worker/tests/test_llm_tool.py`

- [ ] Write failing tests for fixture mode and missing API key behavior.
- [ ] Implement `LLMTool.generate_json(task, inputs, schema_name)` with fixture-backed local mode.
- [ ] Ensure raw model output and validation errors can be saved as artifacts by callers.
- [ ] Run `python -m pytest`.
- [ ] Commit: `feat(agent): add llm json tool boundary`.

## Task 3: Structure Extraction Pipeline

**Files:**
- Create: `packages/prompts/agents/structure_analyst.md`
- Create: `services/worker/app/pipelines/structure_pipeline.py`
- Create: `services/worker/tests/fixtures/sample_analysis.json`
- Create: `services/worker/tests/test_structure_pipeline.py`

- [ ] Write failing tests that turn sample analysis fixture into valid `VideoStructure`.
- [ ] Implement deterministic fallback structure extraction using the segment/slot/rhythm rules specified above.
- [ ] Add prompt instructing the model to migrate structure only, not copy sample content.
- [ ] Validate output against `video-structure.schema.json`.
- [ ] Run `python -m pytest`.
- [ ] Commit: `feat(agent): extract video structure`.

## Task 4: Asset Inventory And Slot Mapping

**Files:**
- Create: `packages/prompts/agents/slot_mapper.md`
- Create: `services/worker/app/pipelines/generation_pipeline.py`
- Create: `services/worker/tests/test_slot_mapping.py`

- [ ] Write failing tests for user brief to `AssetInventory`.
- [ ] Write failing tests for matching `StructureSlot` to assets by type and semantic tags.
- [ ] Implement deterministic `build_asset_inventory` and `map_slots` using the scoring algorithm specified above.
- [ ] Validate inventory against `asset-inventory.schema.json`.
- [ ] Run `python -m pytest`.
- [ ] Commit: `feat(agent): add inventory and slot mapping`.

## Task 5: Gap Report And Generation Plan

**Files:**
- Create: `packages/prompts/agents/gap_planner.md`
- Create: `packages/prompts/agents/storyboard_writer.md`
- Create: `packages/prompts/agents/packaging_designer.md`
- Modify: `services/worker/app/pipelines/generation_pipeline.py`
- Create: `services/worker/tests/test_generation_plan.py`

- [ ] Write failing tests for missing/weak slot detection.
- [ ] Implement P0 completion strategies: `text_completion`, `packaging_completion`, `asset_reuse`.
- [ ] Generate storyboard and `RenderTimeline` using the timeline rules specified above.
- [ ] Validate outputs against `gap-report.schema.json` and `generation-plan.schema.json`.
- [ ] Run `python -m pytest`.
- [ ] Commit: `feat(agent): generate gap report and generation plan`.

## Verification

Run before handoff:

```powershell
cd services/worker
python -m pytest
python -m compileall app
```

Also run:

```powershell
cd packages/contracts
npm run validate:schemas
```

## Acceptance Criteria

- A fixture-only test can produce all four artifacts without external model access.
- Every output artifact validates against the corresponding contract schema.
- Missing and weak slots include human-readable reasons and impacts.
- `GenerationPlan.timeline` can be passed directly to the HyperFrames render plan fixture without shape changes.
- Prompts exist for LLM-backed improvement, but deterministic local behavior remains the default test path.
