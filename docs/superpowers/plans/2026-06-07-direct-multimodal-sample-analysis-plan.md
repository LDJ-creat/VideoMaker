# 直连多模态样例分析实施计划

**Status:** implemented on `main` (2026-06-07)

## 目标

在 Map-Reduce 样例分析之外，新增可选 **视频理解 provider + 用户开关 + 直连多模态结构分析** 路径。配置齐全且开关开启时走 Doubao/Ark 单次视频理解出结构；否则保持传统链路。直连失败 **fail-fast**，不自动降级。

## 模块范围

| 模块 | 变更 |
|------|------|
| `packages/contracts` | `StructureAnalysisRoute`、`structureAnalysisRoute?`、stage `extracting_structure_direct` |
| `services/shared/model_gateway` | `videoUnderstanding` provider、preferences 表、route preview |
| `services/api` | GET/PUT preferences、`videoUnderstanding` probe |
| `services/worker` | `video_structure_analyst`、direct pipeline、p0 路由、checkpoint |
| `apps/web` | settings provider 卡片、直连开关、route 预览、Workbench badge |

## 路由规则

```text
directMultimodalAnalysisEnabled == false → map_reduce
videoUnderstanding configured + hasApiKey + 开关 true → direct_multimodal
否则 → map_reduce
```

## Worker 环境变量

| Env | 默认 | 含义 |
|-----|------|------|
| `VIDEOMAKER_VIDEO_UNDERSTANDING_MAX_MB` | `50` | 直连上传视频体积上限（MB），超出 fail-fast |
| `VIDEOMAKER_VIDEO_UNDERSTANDING_MAX_SEC` | `300` | 直连允许的最长样例时长（秒） |

## 验收

- 单测：`services/shared/tests/test_model_gateway_preferences.py`、`services/worker/tests/test_analysis_route.py`、`services/worker/tests/test_direct_video_structure_pipeline.py`
- E2E：`docs/demos/direct-multimodal-analysis-e2e-checklist.md`

## 不在范围

- 删除或弱化 Map-Reduce 链路
- 直连失败自动 fallback 传统链路
- 与 `video`（AIGC 生视频）provider 混用
