# P1 Demo Checklist

P0 infrastructure checks still apply — see [`p0-demo-checklist.md`](./p0-demo-checklist.md) for upload, SSE/polling, and fixture fallback.

**Fixture / CI path** (`VIDEOMAKER_FIXTURE_MODE=true` or test defaults): no live model keys or HyperFrames CLI required.

**Live demo path**: configure ModelGateway env vars per `docs/superpowers/plans/2026-05-29-videomaker-p1-implementation-plan.md` §18.

---

## P1 core loop

- [ ] Upload sample video → analysis completes with LLM `VideoStructure` (narrative / rhythm / packaging / slots)
- [ ] Structure board shows **evidence** links on keyframes and transcript segments
- [ ] Enter product brief + mixed user assets → inventory shows asset tags and **recommended hook / mid / CTA moments**
- [ ] Slot mapping panel shows semantic **matchReason** per slot
- [ ] Gap panel shows weak/missing slots with chosen **provider** per slot (`hyperframes_material`, `image_generation`, `video_generation`, `tts`, `asset_reuse`)
- [ ] `POST /api/projects/{id}/generation-plan` spawns **two** tasks: **高点击版** (`high_click`) and **高转化版** (`high_conversion`)
- [ ] Multi-task progress panel tracks both generation tasks (SSE primary, polling fallback)
- [ ] Variant tabs compare storyboard / timeline side by side
- [ ] At least **one** AI-generated video clip is produced (quota: max 1 `video_generation` per `generationId`)
- [ ] At least one **HyperFrames** benefit-card / packaging clip appears in artifacts or timeline
- [ ] TTS voiceover is audible in final demo preview (live APIs) or fixture `.wav` artifact (fixture mode)
- [ ] NL revise: enter 「开头更抓人，字幕少一点」→ new generation shows parsed **EditIntent** + diff vs source variant
- [ ] Retry failed task resumes from checkpoint on the **same** LLM path (no rule-based semantic fallback)

---

## Observability (optional late P1)

- [ ] `GET /api/settings/model-gateway` returns capability status **without** API keys
- [ ] `GET /api/generations/{id}/agent-runs` lists persisted agent run logs for debugging

---

## Verification commands (integration branch gate)

```powershell
cd packages/contracts
npm run check
npm run validate:schemas

cd ../../services/api
python -m pytest
python -m compileall app

cd ../worker
python -m pytest
python -m compileall app

cd ../../apps/web
npm run typecheck
npm run test
```
