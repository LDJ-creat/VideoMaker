# Composition Author Brief Plan

**Status:** implemented  
**E2E checklist:** `docs/demos/composition-author-brief-e2e-checklist.md`

## Goal

Storyboard scenes that use HyperFrames material include structured **`compositionAuthorBrief`** (`mode` + `authorPrompt`, optional `templatePreference` / `displayCopyPolicy`). The brief flows through `finishBrief` into `material_author` as the primary HF authoring spec.

## Contracts

- `packages/contracts/schemas/composition-author-brief.schema.json`
- `StoryboardScene.compositionAuthorBrief?` on script-draft / generation-plan
- `FinishBrief.compositionAuthorBrief?`

## Worker

- `services/worker/app/pipelines/composition_brief.py` — HF slot detection, normalize, env `VIDEOMAKER_COMPOSITION_BRIEF_MODE`
- `services/worker/app/agents/storyboard_writer.py` — preserve + validate brief on storyboard phases
- `services/worker/app/providers/finish_brief.py` — copy brief from storyboard; merge packaging `displayCopy`
- `services/worker/app/providers/hyperframes_material_provider.py` — always build finish brief for HF actions

## Composition

- `services/composition/composition/author/payload.py` — top-level `compositionAuthorBrief` in author payload
- `services/composition/composition/author/forbidden_copy_guard.py` — forbid verbatim `authorPrompt`

## Prompts

- `packages/prompts/agents/storyboard_writer.md` — when/how to emit brief
- `packages/prompts/agents/material_author.md` — brief as primary spec
- `packages/prompts/agents/packaging_designer.md` — timeline presets only; no HF layer design

## Out of scope (v1)

- Workbench UI for editing brief
- v2 structured fields (`layerPlan`, `motionBeats`, `registryHints`)
