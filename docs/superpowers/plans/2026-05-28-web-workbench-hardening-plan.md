# Web Workbench Hardening Plan (Implemented)

> Fixes from code review: BFF proxy, SSE `task` events, explicit fixture policy, API-driven views, error handling, and UX polish.

## Completed

- [x] Next.js BFF proxy (`app/api/[...path]`, `lib/server/proxy.ts`)
- [x] Server-only `VIDEOMAKER_API_URL` and `VIDEOMAKER_USE_FIXTURE_FALLBACK`
- [x] Client `apiClient` uses same-origin `/api/*` without silent fixture catch
- [x] `useTaskProgress` listens for `task` SSE events; stops on terminal status
- [x] `ProjectWorkbench` loads structure/generation from API after task success
- [x] `ApiClientError`, upload/URL validation, `DataSourceBanner`
- [x] Projects `sessionStorage` persistence
- [x] Gap empty states, timeline clamp, `GenerationResultView.showTimeline`
- [x] Tests and `apps/web/README.md`

## Verification

```powershell
cd apps/web
npm run test
npm run typecheck
npm run build
cd ../../packages/contracts
npm run check
```
