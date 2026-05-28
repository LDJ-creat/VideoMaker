# P0 Demo Checklist

- [ ] API `/health` returns `{ "ok": true }`
- [ ] Create project via UI or `POST /api/projects`
- [ ] Local sample upload registers file under `storage/projects/{projectId}/samples/`
- [ ] URL import returns `taskId` and streams progress (uploading → analysis → structure)
- [ ] Page refresh restores task state from polling endpoint
- [ ] Sample analysis shows metadata / transcript / shots in workbench
- [ ] `VideoStructure` visible in structure board
- [ ] Brief and assets saved via API
- [ ] Generation task produces `GapReport` and `GenerationPlan`
- [ ] Timeline preview renders tracks
- [ ] HyperFrames preview link opens `preview.html`
- [ ] Fixture fallback still works when API is down (`VIDEOMAKER_USE_FIXTURE_FALLBACK=true`)
