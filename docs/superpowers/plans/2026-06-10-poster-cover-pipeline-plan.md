# Poster 封面管线

> **状态：** 已实现（2026-06-10）  
> **关联 UI：** [2026-06-09-knowledge-template-ui-spec.md](../specs/2026-06-09-knowledge-template-ui-spec.md)

## 目标

将 UI 封面（poster）与结构分析 keyframe 解耦：独立 `poster.jpg`、三帧择优抽取、统一封面解析优先级。

## 存储

| 路径 | 用途 |
|------|------|
| `storage/projects/{projectId}/samples/{sampleId}/poster.jpg` | 样例 UI 封面 |
| `storage/projects/{projectId}/renders/{generationId}/poster.jpg` | 成片 UI 封面 |
| `.../analysis/keyframes.json` | 保留 — 仅 map-reduce / LLM 视觉；legacy fallback |

## 抽取

- 模块：`services/shared/video/poster.py` → `extract_video_poster`
- 采样 `t ∈ {1.0, 1.5, 2.0}s`（跳过片头模糊），OpenCV Laplacian 择优；短视频自动回退更早时间点
- 源视频 mtime 未变且 poster 已存在时可 skip（resume 友好）

## 读取优先级

**Category 模板库：** entry 按 `updatedAt` 降序 → 第一个 importable 且源样例有 poster 的 entry。

**项目列表 `coverUrl`：** 最新成功成片 poster → `primarySampleId` → `referenceSampleIds` → 其余样例（`createdAt`）→ 占位。

**样例 `posterUrl`：** `poster.jpg` → legacy keyframes max score。

## 写入触发

1. API `upload_sample` / batch upload — 同步 extract，失败 log warning，不阻塞 201
2. Worker `extracting_poster` stage — 始终执行（与 direct_multimodal 无关）
3. FFmpeg / HyperFrames render 成功且 `output.mp4` size > 0
4. `sample_seed_service` — 复制源 poster 或 re-extract

## API

- `GET /api/projects` — `ProjectSummary.coverUrl`
- 媒体 URL 走现有 `/api/projects/{id}/media/file/...`

## 历史回填

```powershell
cd services/api
python scripts/backfill_posters.py --dry-run
python scripts/backfill_posters.py
python scripts/backfill_posters.py --project-id <uuid>
```

默认 storage 根目录为 `services/api/storage`（与本地 API dev 一致）。

## 验证

```powershell
cd services/shared && python -m pytest tests/test_poster.py
cd services/api && python -m pytest tests/test_poster_service.py tests/test_sample_keyframes_route.py tests/test_knowledge_category_routes.py tests/test_sample_seed_service.py
cd services/worker && python -m pytest tests/test_sample_pipeline_poster.py tests/test_ffmpeg_backend.py
cd apps/web && npm run typecheck && npm run test -- tests/projects-home.test.tsx
```

## v1 不在范围

- SQLite `projects.cover_uri` 缓存列
- Promote 时 copy poster 到 `storage/knowledge/{slug}/{entryId}/poster.jpg`
- 替换 OpenCV 全量 keyframe 抽取
