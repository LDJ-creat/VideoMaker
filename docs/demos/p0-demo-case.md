# P0 Demo Case

## Input Assumptions

- Sample video: 15–60s vertical short-form ad or product clip with clear hook, benefit, and CTA beats.
- User brief: topic, product name, 2–5 selling points, optional target audience.
- Optional user assets: 1–3 images or short clips plus caption text.

## Expected Outputs

1. `VideoStructure` with narrative segments, rhythm profile, and structure slots.
2. `GapReport` with matched, weak, and missing slots.
3. `GenerationPlan` with storyboard, packaging plan, and `RenderTimeline`.
4. HyperFrames `preview.html` under `storage/projects/{projectId}/renders/{generationId}/`.

## Start Services

```powershell
# Terminal 1 — API (from repo root or worktree)
cd services/api
python -m uvicorn app.main:app --reload --port 8000

# Terminal 2 — Web (BFF proxies to API)
cd apps/web
$env:NEXT_PUBLIC_API_BASE_URL = "http://127.0.0.1:8000"
npm run dev
```

Set `VIDEOMAKER_USE_FIXTURE_FALLBACK=false` in `apps/web/.env.local` when running against the real API.

## Demo Flow

1. Open `/projects` and create a project (or open an existing `projectId`).
2. Upload a local sample **or** import a URL — URL import shows the same task progress UI.
3. Click **开始样例分析** for local uploads (URL import runs analysis automatically).
4. Review analysis, structure slots, then save brief and upload assets.
5. Click **开始生成计划** and watch SSE progress through mapping, planning, and render.
6. Refresh the browser during a running task — progress resumes via `GET /api/tasks/{taskId}`.
