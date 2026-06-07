# Pexels 素材库集成计划

**Status:** implemented

**目标：** 在 gap 补全链路中插入 Pexels stock 搜索层（`stock_media_search`），位于用户素材复用之后、AIGC 之前；未配置 API key 或搜索未命中时 seamless fallback。

## 已实现能力

### Workstream A — 契约

- `completionActions.strategy/provider` 新增 `stock_media_search`
- `stock-search-query.schema.json`、`stock-attribution.schema.json`
- `CompletionAction.stockSearchQuery` / `stockAttribution`；`GeneratedBy` 扩展 photographer/pageUrl

### Workstream B — Worker

- `app/tools/pexels_tool.py` — Photos/Videos Search + download（fixture 模式）
- `app/stock/stock_eligibility.py` — product_bound / product_closeup 硬禁
- `app/agents/stock_query_author.py` + prompt — LLM 主路径生成英文 query
- `app/stock/stock_query_builder.py` — 确定性兜底
- `app/stock/stock_scorer.py` — 候选打分
- `app/providers/stock_media_provider.py` — 搜索/下载/trim + fallback AIGC
- `gap_selection.py` — stock 优先于 video/image generation（当 Pexels 已配置）

### Workstream C — API

- SQLite `stock_media_providers`
- `GET/PUT /api/settings/stock-media`、`POST .../test`
- `pipeline_runner` 注入 `VIDEOMAKER_PEXELS_API_KEY`

### Workstream D — Web

- `StockMediaSettingsPanel`（设置页）
- `GeneratedAssetBadge` — 「Pexels 素材」+ 摄影师 tooltip

## 环境变量

| 变量 | 默认 | 含义 |
|------|------|------|
| `VIDEOMAKER_PEXELS_API_KEY` | 空 | Pexels Authorization |
| `VIDEOMAKER_STOCK_MEDIA_ENABLED` | true | 全局开关 |
| `VIDEOMAKER_STOCK_MATCH_MIN_SCORE` | 0.55 | 接受候选最低分 |
| `VIDEOMAKER_STOCK_MAX_CANDIDATES` | 5 | 每 query 评估条数 |

## 测试

```powershell
cd packages/contracts
npm run check; npm run validate:schemas

cd services/worker
python -m pytest tests/test_stock_eligibility.py tests/test_stock_query_builder.py tests/test_pexels_tool.py tests/test_stock_media_provider.py tests/test_gap_selection.py -q

cd services/api
python -m pytest tests/test_stock_media_settings_route.py -q

cd apps/web
npm run typecheck
npm run test -- tests/stock-media-badge.test.tsx
```

## E2E

见 `docs/demos/pexels-stock-media-e2e-checklist.md`。
