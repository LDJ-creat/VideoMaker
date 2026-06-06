# Sample Structure Output v3 — Implementation Record

**Status:** Implemented on branch `feature/sample-structure-output-v3` (or current workspace).

**Standard:** [docs/standards/sample-video-structure-extraction-standard.md](../standards/sample-video-structure-extraction-standard.md) v1.1

## Summary

- **VideoStructure** is **p1-v3 only** (breaking). Legacy `p0-v1` / `p1-v2` / top-level `packaging` removed from schema.
- v3 blocks: `context`, `verbal`, `visual`, `audio`, `transfer`, `analysisQuality.promoteReady`.
- Coercer `_enrich_v3_blocks` deterministically fills L2 fields; LLM fills L0/L1.
- Old test storage: **delete `samples/*/analysis` only** — do not auto-analyze. Optional: `scripts/migrate-video-structure-v2-to-v3.ps1 -Apply`.

## Verification

```powershell
cd packages/contracts && npm run check && npm run validate:schemas
cd services/worker && python -m pytest tests/test_structure_coercer.py tests/test_structure_validator.py tests/test_structure_quality.py tests/test_sample_facts.py -q
cd services/api && python -m pytest tests/test_sample_analysis_service.py -q
cd apps/web && npm run typecheck && npm run test
```

## Old data policy

- No startup/CI batch analyze.
- Promote requires `version=p1-v3` and `analysisQuality.promoteReady=true`.
