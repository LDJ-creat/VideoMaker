# 样例分析成本与韧性改造计划

**Status:** implemented on `feature/sample-analysis-depth`

**目标：** 降低快切/长片样例的 vision 成本与 retry 开销；batch 失败时不丢已成功结果；口播类视频优先走 text + digest 路径。

## 已实现能力

### Workstream A — Batch vision 逐批落盘

- Artifact: `analysis/batch-digests/batch-{index}.json`, `analysis/visual-facts-progress.json`
- 每批成功后增量更新 `sample-analysis.json`（`keyframeBatchDigests`, `onScreenTextFacts`, `warnings`）
- 单批失败写 `vision_batch_{i}_failed:{Exception}` 到 `warnings`，停止后续 batch
- Retry 跳过已有 `batch-{i}.json`；覆盖率 ≥ `VIDEOMAKER_VISION_BATCH_MIN_COVERAGE` 时 stage 可降级完成

**代码：** `services/worker/app/perception/visual_facts_progress.py`, `sample_facts.py`, `runtime/checkpoint.py`

### Workstream B — 关键帧采样

- `keyframe_sampler.select_keyframes_for_llm()`：短镜头合并 → 全片 cap → 均匀采样 + 保留首尾
- `keyframes.json` / 磁盘全量不变，仅 LLM 输入被 cap

**代码：** `services/worker/app/perception/keyframe_sampler.py`

### Workstream C — P2 去重 vision

- `digest_coverage.resolve_segment_vision_policy()`：digest 覆盖 segment 时 `segment_analyst` 走 text profile
- `VideoStructure.analysisQuality.warnings` 记录 `segment_{id}_vision_skipped_digest_coverage`

**代码：** `services/worker/app/perception/digest_coverage.py`, `agents/segment_analyst.py`, `pipelines/structure_analysis_pipeline.py`

### Workstream D — 分析档位

- `analysis_depth.resolve_analysis_depth()`：`fast` / `standard` / `deep`（auto 时口播+快切 → fast）
- `sample-analysis.json` 写入 `analysisDepth`

**代码:** `services/worker/app/perception/analysis_depth.py`, `packages/contracts/src/sample-analysis-types.ts`

## 环境变量

| 变量 | 默认 | 含义 |
|------|------|------|
| `VIDEOMAKER_ANALYSIS_DEPTH` | auto | fast / standard / deep |
| `VIDEOMAKER_KEYFRAME_MAX_PER_VIDEO` | 按 duration 公式 | LLM 帧硬上限 |
| `VIDEOMAKER_SHOT_MERGE_MAX_SEC` | 1.0 | 短镜头合并阈值 |
| `VIDEOMAKER_VISION_BATCH_MIN_COVERAGE` | 0.67 | partial batch 完成 stage 最低比例 |
| `VIDEOMAKER_SEGMENT_VISION_MIN_COVERAGE` | 0.6 | 低于此才 segment vision |

## 测试

```powershell
cd services/worker
python -m pytest tests/test_visual_facts_resilience.py tests/test_keyframe_sampler.py tests/test_segment_analyst_vision_policy.py -q
```

## E2E

见 `docs/demos/sample-analysis-depth-e2e-checklist.md` § 成本与韧性验收。
