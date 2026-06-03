# Master Narration Layer (档 A) — Implementation Plan

## Decision

Keep **storyboard + compose** (no end-to-end video gen). Introduce a **full-video narrative layer** before per-scene scripts using **档 A**: one `storyboard_writer` LLM call returns two-phase JSON:

```json
{
  "masterNarration": "整段可朗读口播",
  "storyboard": [{ "slotId", "visual", "script", ... }]
}
```

## Pipeline change

```text
planning_completion
  → storyboard_writer (masterNarration + storyboard)
  → apply_master_narration_to_storyboard (align / split scripts)
  → packaging_designer
  → assemble_generation_plan (persist masterNarration)
  → TTS / subtitles from per-scene script
```

## Files

| Area | File | Change |
|------|------|--------|
| Contracts | `generation-plan.schema.json`, `types.ts` | Required `masterNarration` |
| Prompt | `storyboard_writer.md` | Two-phase output spec |
| Worker | `master_narration.py` | Clause split + duration-weighted scene split |
| Worker | `storyboard_writer.py` | Validate + post-process |
| Worker | `generation_pipeline.py` | Wire master through planning |
| Worker | `revise_pipeline.py` | Snapshot `masterNarration` |
| Tests | `test_master_narration.py`, fixtures | TDD coverage |

## Split algorithm

1. Split `masterNarration` on Chinese/Western sentence boundaries.
2. Allocate clauses to scenes by `endSec - startSec` duration weights.
3. Keep scene `script` when it is a substring of master and not creative-direction text; else use split chunk.

## Compatibility

- `assemble_generation_plan`: derives `masterNarration` from concatenated scene scripts when omitted (fixtures / legacy).
- Revise snapshot stores both `storyboard` and `masterNarration` for partial reruns.

## Verification

```powershell
cd packages/contracts && npm run check && npm run validate:schemas
cd services/worker && python -m pytest tests/test_master_narration.py tests/test_storyboard_writer.py tests/test_generation_plan.py -q
cd apps/web && npm run typecheck
```
