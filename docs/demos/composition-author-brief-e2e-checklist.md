# Composition Author Brief E2E Checklist

## Prerequisites

- API + worker running with live LLM (or fixture mode with updated storyboard fixtures containing `compositionAuthorBrief`)
- `VIDEOMAKER_COMPOSITION_BRIEF_MODE=require` (default)

## 1. Storyboard output

1. Run generation on **high_conversion** variant with packaging slots (benefit_card / hook_text).
2. Open `storage/projects/{projectId}/generations/{generationId}/script-draft.json`.
3. Confirm HF-related scenes include:

```json
"compositionAuthorBrief": {
  "mode": "hf_native",
  "authorPrompt": "...",
  "templatePreference": "benefit-card"
}
```

4. Confirm pure `generated` B-roll scenes **omit** `compositionAuthorBrief`.

## 2. Finish brief + material author payload

1. After material stage starts, inspect agent run or react trace for `material_author`.
2. Confirm user payload includes top-level `compositionAuthorBrief` copied from storyboard.
3. Confirm `finishBrief.creativeBrief.visualDirection` is **not** used when brief is present.

## 3. Render quality smoke

1. Complete generation to MP4.
2. HF slots: no verbatim VO duplicated inside clip (subtitles on timeline only).
3. `source_then_polish` slots: base video visible with overlay polish.

## 4. Env fallback

1. Set `VIDEOMAKER_COMPOSITION_BRIEF_MODE=warn` — missing brief logs warning but generation continues.
2. Set `VIDEOMAKER_COMPOSITION_BRIEF_MODE=off` — no brief validation.

## 5. Revise boundary

1. Run NL revise with packaging-only patch — `compositionAuthorBrief` on storyboard unchanged unless storyboard rerun.
2. Storyboard-targeted revise updates brief on affected scenes.
