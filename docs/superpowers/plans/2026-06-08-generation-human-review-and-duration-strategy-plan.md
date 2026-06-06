# Generation Human Review and Duration Strategy Plan

**Date:** 2026-06-08  
**Status:** Implemented

## Summary

Introduces target duration configuration, per-variant script review gates (master narration + storyboard), and short/long generation strategies split at 60 seconds.

## User flow

1. User sets `durationTarget` on Brief (workbench **目标时长** panel; recommendation from sample structure).
2. `POST .../generation-plan` spawns worker with `humanReviewMode` (default true).
3. After mapping/gap, worker drafts master script → pauses (`status=awaiting_review`, stage `awaiting_master_review`).
4. User edits/approves via **脚本审核** panel → `POST .../approve-master` → worker drafts storyboard → pauses at `awaiting_storyboard_review`.
5. User approves storyboard → `POST .../approve-storyboard` → worker chooses `short_form_direct` (≤60s) or `long_form_composed` (>60s) and continues material/render.

## Artifacts

- `generations/{generationId}/duration-target.json`
- `generations/{generationId}/structure-scaled.json`
- `generations/{generationId}/script-draft.json` (per variant)

## Contracts

- `UserBrief.durationTarget`
- `ScriptDraft` schema
- `TaskEvent.status`: `awaiting_review`
- New stages: `drafting_master_script`, `awaiting_master_review`, `drafting_storyboard`, `awaiting_storyboard_review`, `producing_media`

## API

- `GET /api/projects/{id}/duration-recommendation`
- `GET|PUT /api/generations/{id}/script-draft`
- `POST /api/generations/{id}/approve-master`
- `POST /api/generations/{id}/approve-storyboard`

## Worker modules

- `duration_target.py`, `generation_strategy.py`, `script_draft.py`, `short_form_direct.py`
- `generation_pipeline.run_script_drafting` phases; `p0_demo_pipeline` pause/resume

## CI / legacy

Set `VIDEOMAKER_HUMAN_REVIEW_MODE=false` for one-shot generation without gates.

## Verification

- `services/worker/tests/test_duration_target.py`
- `services/worker/tests/test_generation_strategy.py`
- `services/worker/tests/test_short_form_direct.py`
- `services/api/tests/test_duration_recommendation_route.py`
- `services/api/tests/test_script_draft_routes.py`
- `apps/web/tests/duration-target-labels.test.ts`
- `apps/web/tests/script-review-panel.test.tsx`
- E2E: `docs/demos/generation-script-review-e2e-checklist.md`
