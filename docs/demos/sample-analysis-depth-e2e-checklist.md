# Sample Analysis Depth E2E Checklist

1. Upload a 30–60s vertical sample with voiceover + BGM.
2. Run analyze → confirm `sample-analysis.json` contains `audioProfile` and optional `keyframeBatchDigests`.
3. Open sample analysis tab → script technique differs from structure evidence primary text.
4. Structure slots show diverse roles + non-empty `migrationTemplate`.
5. No `critical:` warnings in `analysisQuality.warnings`; knowledge promote succeeds.
6. Start generation → storyboard `visual` uses concrete camera language from `visualSpec`.

## 成本与韧性验收

7. 上传 3min 快切口播样例 → `keyframes.json` 仍保留全量镜头帧，但 `visual-facts-progress.json` 的 `totalBatches` 对应采样后 batch 数（≤6）。
8. 模拟 batch 失败（如 quota）→ 磁盘有 `batch-digests/batch-0.json` 等部分文件，`sample-analysis.json` 的 `warnings` 含 `vision_batch_N_failed`；retry 不重复已成功 batch。
9. 结构分析完成 → `segment-analyses.json` + `video-structure.json`；口播片 `analysisQuality.warnings` 可含 `segment_*_vision_skipped_digest_coverage`。
10. 对比改造前日志/mock：总 vision 调用次数下降 ≥50%（P2 segment 不再重复送图）。

Verification commands:

```powershell
cd packages/contracts
npm run check
npm run validate:schemas

cd services/worker
python -m pytest
python -m compileall app

cd services/api
python -m pytest
python -m compileall app

cd apps/web
npm run typecheck
npm run test
```
