# VideoMaker Web Workbench

Next.js frontend for the P0 structure migration workbench.

## Architecture

Browser requests use **same-origin** paths (`/api/...`). Next.js Route Handlers in `app/api/[...path]` proxy to FastAPI (`VIDEOMAKER_API_URL`). This avoids CORS and keeps the backend URL server-only.

```text
Browser → /api/* (Next BFF) → VIDEOMAKER_API_URL/api/*
```

SSE task progress uses `EventSource` on `/api/tasks/{taskId}/events` with `event: task` (proxied stream).

## Setup

```powershell
cd apps/web
cp .env.example .env.local
npm install
npm run dev
```

Open http://localhost:3000

## Environment

| Variable | Default | Description |
|----------|---------|-------------|
| `VIDEOMAKER_API_URL` | `http://127.0.0.1:8000` | FastAPI base URL (server-only) |
| `VIDEOMAKER_USE_FIXTURE_FALLBACK` | `false` | BFF returns fixtures when upstream fails |

Deprecated: `NEXT_PUBLIC_API_BASE_URL` — no longer used; do not configure browser-direct backend URLs.

## Scripts

```powershell
npm run dev
npm run test
npm run typecheck
npm run build
```

## Gap report API

There is no dedicated `GET /api/gap-reports/{id}` in P0. Gap data may arrive embedded in generation responses during integration; until then use **加载演示数据** or fixture fallback with the banner shown in the UI.
