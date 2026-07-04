# Evaluation System E2E Checklist

## 前置

- [ ] API + Worker 已启动（`services/api/run-dev.ps1`）
- [ ] `VIDEOMAKER_EVAL_ENABLED=true`（默认）
- [ ] 至少配置一个 text provider；可选 TTS / image / video provider

## 1. 生成完成自动报告

1. 完成一次 generation（含或不含 human review gate）。
2. 检查磁盘：
   - `storage/projects/{projectId}/generations/{generationId}/evaluation-report.json`
3. 报告应包含：
   - [ ] `profile.inputMode`（`sample_migration` | `knowledge_guided` | `greenfield`）
   - [ ] `scores.core`（technical / plan / perceptual / weighted）
   - [ ] `observability.usageByCategory` 按 billingUnit 分卡（无跨类总 token）
   - [ ] `observability.timing.wallClock.humanWaitMs`（若经过 gate）
   - [ ] `observability.timing.stages[]`（含 `kind: human_gate` 若适用）
   - [ ] `observability.timing.modelLatency`

## 2. Gate partial 报告

1. 在 `awaiting_master_review` / `storyboard` / `material_review` 暂停时检查：
   - `evaluation-report.partial.json`
2. [ ] `partial: true`；无最终 MP4 时 L0 technical 可为 0 或跳过

## 3. API lazy build + rebuild

```http
GET  /api/generations/{generationId}/evaluation
POST /api/generations/{generationId}/evaluation/rebuild
```

- [ ] 删除 `evaluation-report.json` 后 GET 可 lazy 重建（`VIDEOMAKER_EVAL_LAZY_BUILD=true`）
- [ ] POST rebuild 覆盖旧报告，**不重跑** pipeline
- [ ] `OBSERVABILITY_CAPTURE=off` 历史任务 `observability.incomplete: true`

## 4. Run 级汇总

```http
GET /api/projects/{projectId}/generation-runs/{runId}/evaluation-summary
```

- [ ] 双变体 run 返回 `variants[]` 含各 generation 的 verdict / scores / observability

## 5. 工作台 EvaluationPanel

- [ ] Result 区展示质量分、五类用量、墙钟与阶段条形图
- [ ] 生视频 jobs 表展示 `requestedDurationSec` / `actualDurationSec`
- [ ] 「重算」按钮调用 rebuild API

## 6. 样例分析（M5）

- [ ] 样本分析成功后：`samples/{sampleId}/analysis/evaluation-report.json`
- [ ] `modules.sample_analysis.scope = sample`

## 7. 三种 inputMode

| 场景 | 期望 |
|------|------|
| 真实 sample 迁移 | `enabledModules` 含 `migration` |
| knowledge 引导 | 含 `knowledge_fit` |
| greenfield | 仅 `core`，无 migration |

## 8. bench / 单测

```powershell
cd services/shared/evaluation
python -m pytest tests -q

cd services/api
python -m pytest tests/test_evaluation_routes.py -q

cd packages/contracts
npm run check
npm run validate:schemas
```
