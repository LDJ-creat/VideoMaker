# Multi-Sample Analysis and Structure Synthesis

**Status:** Implemented 2026-06-04.

**Goal:** Support multi-file sample upload, parallel analysis, batch-aware sample selection, structure synthesis from primary + reference samples, and generation run history.

## Contracts

- `UploadBatch`, `SampleRecommendation`, `ProjectSampleSelection`, `StructureProvenance`, `GenerationRun`
- Schemas under `packages/contracts/schemas/`

## Storage

```text
storage/projects/{projectId}/
  samples/{sampleId}/analysis/video-structure.json
  generations/{generationId}/
    synthesized-structure.json
    structure-provenance.json
```

## SQLite

- `upload_batches`, `project_sample_selection`, `generation_runs`
- `samples.upload_batch_id`, `generations.generation_run_id`

## API

| Method | Path |
|--------|------|
| POST | `/api/projects/{id}/samples/upload-batch` |
| POST | `/api/projects/{id}/samples/analyze-batch` |
| GET | `/api/projects/{id}/upload-batches` |
| POST | `/api/projects/{id}/samples/recommend` |
| GET/PUT | `/api/projects/{id}/samples/selection` |
| POST | `/api/projects/{id}/samples/selection/reset` |
| GET | `/api/projects/{id}/generation-runs` |
| GET | `/api/projects/{id}/generation-runs/{runId}` |

`POST .../generation-plan` accepts optional `sampleSelection` and returns `generationRunId`.

## Worker

- `structure_synthesizer` agent in `run_generation` when reference structures present
- Fixture mode: primary structure + fallback provenance

## Frontend

- Multi upload in `SampleInputPanel`
- `SampleSelectionPanel`, `SampleBatchAnalysisProgress`, `GenerationRunHistoryPanel`

## Verification

```powershell
cd packages/contracts && npm run check && npm run validate:schemas
cd services/api && python -m pytest tests/test_sample_selection_routes.py
cd services/worker && python -m pytest tests/test_structure_synthesizer_agent.py
cd apps/web && npm run typecheck
```
