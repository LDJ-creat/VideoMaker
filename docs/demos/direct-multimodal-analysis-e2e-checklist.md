# 直连多模态样例分析 E2E 验收清单

## 前置

- API / Worker / Web 已启动，且 `VIDEOMAKER_FIXTURE_MODE` 未开启（Live 模式）
- 在 `/settings` 可访问 Model Gateway 配置页

## 1. 仅 text/vision → 传统 Map-Reduce

1. 配置 `text`、`vision`（可不配置 `videoUnderstanding`）
2. 确认状态卡片显示：**当前样例分析将使用：传统 Map-Reduce**
3. 对任意样例执行 analyze
4. 验收：
   - `sample-analysis.json` 中 `structureAnalysisRoute` 为 `map_reduce`（或缺省）
   - 存在 `batch-digests/` 或 `keyframeBatchDigests`（视觉批次链路）
   - 任务 stage 经过 `extracting_visual_facts` → `proposing_segments` 等

## 2. 配置 videoUnderstanding + 开关 ON → 直连

1. 在 `/settings` 配置 **视频理解** provider（Ark baseUrl + model + API Key）
2. 保持 **启用直连多模态样例分析** 为开启
3. 确认预览为 **直连多模态**
4. 对 cb39 或本地样例执行 analyze
5. 验收：
   - 无 `batch-digests/`（直连路径不跑 Map-Reduce 视觉批次）
   - 存在 `video-structure.json`
   - `analysisQuality.warnings` 含 `analysis_route:direct_multimodal`
   - `sample-analysis.json` 中 `structureAnalysisRoute` 为 `direct_multimodal`
   - Workbench 样例详情显示 Badge **直连多模态分析**

## 3. 开关 OFF → 仍走传统链路

1. 即使已配置 `videoUnderstanding`，关闭直连开关并保存
2. 对**新一次** analyze（或清除 checkpoint 后重跑）
3. 验收：`structureAnalysisRoute=map_reduce`，存在 Map-Reduce 中间产物

## 4. 直连失败 fail-fast

1. 开启直连，但故意配置错误 model 或无效 Key
2. 执行 analyze
3. 验收：
   - 任务 `failed`，stage 为 `extracting_structure_direct`
   - `error.code` 为 `direct_multimodal_failed`，`retryable: true`
   - **不**自动生成半成品 `video-structure.json`
4. 关闭直连开关后重新 analyze → 可走传统 Map-Reduce

## 5. Resume 路由锁定

1. 以 Map-Reduce 跑至中途 checkpoint
2. 在 settings 开启直连并配置 provider
3. Retry 同一 task
4. 验收：fail-fast，`analysis_route_mismatch`，提示需重新 analyze

## 6. videoUnderstanding 连通性探测

1. 在 `/settings` 视频理解 Tab 点击 **测试连接**（PR3）
2. 有效凭据应返回「视频理解连接成功」
