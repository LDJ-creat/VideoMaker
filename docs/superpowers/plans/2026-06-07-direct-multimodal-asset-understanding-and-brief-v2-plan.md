# 直连多模态用户资产理解 + Brief v2

**Status:** implemented

## 目标

- UserBrief v2：contentCategory、creativeGoal、subjectName、keyPoints、supplementalNotes，兼容 productName/sellingPoints
- 资产理解主路径：`videoUnderstanding` + `directMultimodalAnalysisEnabled` → `asset_inventory_analyst` 单次/分批多模态
- 降级：未配置 provider 或关闭开关 → legacy（content_strategist + OpenCV + asset_moment_vision）
- 多模态运行时失败 fail-fast（不 silent fallback legacy）
- 用户素材支持 text 文件上传

## 路由

与样例分析共用 `resolve_analysis_route_preview` / `directMultimodalAnalysisEnabled`。

生成产物 `asset-inventory.json` 可选字段：
- `assetUnderstandingRoute`: `direct_multimodal` | `direct_multimodal_batched` | `legacy`
- `assetUnderstandingWarnings`

## Worker 环境变量

| Env | 默认 | 含义 |
|-----|------|------|
| `VIDEOMAKER_VIDEO_UNDERSTANDING_MAX_MB` | `50` | 单视频体积上限 |
| `VIDEOMAKER_VIDEO_UNDERSTANDING_MAX_SEC` | `300` | 单视频时长上限 |
| `VIDEOMAKER_ASSET_UNDERSTANDING_MAX_MEDIA_COUNT` | `6` | 单次多模态 media 数量上限 |
| `VIDEOMAKER_ASSET_UNDERSTANDING_MAX_TOTAL_MB` | `80` | 单次多模态 media 总体积上限 |
| `VIDEOMAKER_ASSET_TEXT_MAX_CHARS` | `8000` | text 资产读取字符上限 |

## 验收

- 单测：`services/worker/tests/test_user_brief_normalize.py`、`test_asset_understanding_route.py`、`test_direct_asset_understanding.py`
- E2E：`docs/demos/direct-multimodal-asset-understanding-e2e-checklist.md`
